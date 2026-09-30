"""Knowledge retrieval: LLM-proposed keywords (MIGRATION #4) + token-overlap scoring.

`propose_keywords` calls `local_engine.complete_json`; any model failure falls back
to deterministic regex tokens, so retrieval NEVER hard-fails (ARCHITECTURE §6).

Phase 10 (MIGRATION #2): :func:`context_block` picks the strategy adaptively -
when the model's context window is >=128k (e.g. MiMo-V2.6 1M) the ENTIRE knowledge
base is inlined and retrieval is skipped; smaller models keep top-K keyword search.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from llm import adapter, local_engine
from llm.schemas import LLMError

from .models import KnowledgeItem

MAX_KEYWORDS = 6
INLINE_KB_MAX_CHARS = 24_000  # safety cap even when the full KB would fit
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "her",
    "was", "one", "our", "out", "has", "have", "this", "that", "with", "from",
    "they", "what", "when", "where", "which", "about", "does", "should", "case",
    "alert", "from", "into", "than", "then", "them", "were", "been", "being",
}


class KeywordList(BaseModel):
    keywords: list[str] = Field(default_factory=list)


def fallback_keywords(query: str) -> list[str]:
    """Deterministic tokens from the query (no LLM)."""
    seen: list[str] = []
    for token in _TOKEN_RE.findall((query or "").lower()):
        if token in _STOPWORDS or token in seen:
            continue
        seen.append(token)
        if len(seen) >= MAX_KEYWORDS:
            break
    return seen


def propose_keywords(query: str) -> list[str]:
    """LLM proposes search keywords for knowledge retrieval (MIGRATION #4)."""
    try:
        result = local_engine.complete_json(
            [
                {
                    "role": "user",
                    "content": (
                        "Propose up to 6 short search keywords for finding knowledge-base "
                        f"entries relevant to this query. Reply as JSON {{\"keywords\": [...]}}.\n\n"
                        f"Query: {query[:600]}"
                    ),
                }
            ],
            schema=KeywordList,
            mode="work",
            max_tokens=200,
        )
        words = [
            w.strip().lower()
            for w in result.keywords
            if isinstance(w, str) and len(w.strip()) >= 3 and w.strip().lower() not in _STOPWORDS
        ]
        if words:
            return words[:MAX_KEYWORDS]
    except LLMError as exc:
        import logging

        logging.getLogger("apps.knowledge").warning("keyword proposal degraded: %s", str(exc)[:150])
    return fallback_keywords(query)


def _expand_terms(keywords: list[str]) -> list[str]:
    """Models often propose multi-word phrases; score phrase + its word tokens."""
    terms: list[str] = []
    for kw in keywords:
        kw = str(kw).strip().lower()
        if not kw or kw in terms:
            continue
        terms.append(kw)
        if " " in kw:
            for token in kw.split():
                if len(token) >= 3 and token not in _STOPWORDS and token not in terms:
                    terms.append(token)
    return terms


def search(query: str, *, top_k: int = 3, propose: bool = False, keywords: list[str] | None = None) -> list[dict]:
    """Score KB items by keyword overlap over title (x3), tags (x2), body (x1)."""
    if keywords is None:
        keywords = propose_keywords(query) if propose else fallback_keywords(query)
    terms = _expand_terms(keywords)
    if not terms:
        return []
    scored: list[dict] = []
    for item in KnowledgeItem.objects.all()[:500]:
        title = item.title.lower()
        body = item.body.lower()
        tags = [str(t).lower() for t in item.tags]
        score = 0
        for kw in terms:
            if kw in title:
                score += 3
            if any(kw in t for t in tags):
                score += 2
            score += body.count(kw)
        if score > 0:
            scored.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "body": item.body,
                    "tags": item.tags,
                    "score": score,
                }
            )
    scored.sort(key=lambda h: (-h["score"], -h["id"]))
    return scored[:top_k]


def _format_hits(hits: list[dict], body_chars: int) -> str:
    if not hits:
        return ""
    return "Relevant knowledge:\n" + "\n".join(
        f"- {h['title']}: {h['body'][:body_chars]}" for h in hits
    )


def _format_full_kb(body_chars: int) -> str:
    lines: list[str] = []
    for item in KnowledgeItem.objects.order_by("-id")[:500]:
        tags = ", ".join(str(t) for t in item.tags)
        suffix = f" [{tags}]" if tags else ""
        lines.append(f"- {item.title}{suffix}: {item.body[:body_chars]}")
    if not lines:
        return ""
    block = "Knowledge base (complete - all entries):\n" + "\n".join(lines)
    if len(block) > INLINE_KB_MAX_CHARS:
        block = block[:INLINE_KB_MAX_CHARS] + "\n... (knowledge base truncated)"
    return block


def context_block(query: str, *, propose: bool = False, body_chars: int = 300) -> str:
    """KB text for a prompt: full inline dump on big-context models, top-K otherwise."""
    if adapter.wants_inline_kb():
        return _format_full_kb(body_chars)
    return _format_hits(search(query, top_k=3, propose=propose), body_chars)
