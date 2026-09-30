"""Knowledge extraction from closed cases (MIGRATION #5).

One `local_engine.complete_json` call per case; skips gracefully when the model is
down (health pre-check) or the output is unusable - never blocks case closure.
Called automatically on case close and by the `extract_knowledge` playbook step (#8).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from apps.cases.context import format_case_context
from llm import local_engine
from llm.health import health_check
from llm.schemas import LLMError

from .models import KnowledgeItem

logger = logging.getLogger("apps.knowledge")

MAX_ITEMS = 5

EXTRACT_SYSTEM = (
    "You extract reusable defensive knowledge from a closed SOC case. Keep only "
    "genuinely transferable learnings (attacker TTPs, hunting guidance, detection "
    "ideas, pitfalls). One knowledge item per distinct learning; short precise title; "
    "body of 2-6 sentences; 0-4 lowercase tags. Return NO items if nothing is reusable."
)


class KnowledgeRecord(BaseModel):
    title: str
    body: str = ""
    tags: list[str] = Field(default_factory=list)


class KnowledgeExtraction(BaseModel):
    items: list[KnowledgeRecord] = Field(default_factory=list)


def extract_for_case(case, actor=None) -> dict:
    """Returns {"created": n, "titles": [...]} or {"skipped": reason}."""
    if not health_check().ok:
        return {"skipped": "model unavailable"}

    context = format_case_context(case)[:8000]
    try:
        result = local_engine.complete_json(
            [{"role": "user", "content": f"Closed case:\n{context}\n\nExtract reusable knowledge."}],
            schema=KnowledgeExtraction,
            system=EXTRACT_SYSTEM,
            mode="work",
            max_tokens=900,
        )
    except LLMError as exc:
        logger.warning("knowledge extraction degraded for %s: %s", case.case_id, str(exc)[:200])
        return {"skipped": f"model error: {exc}"}

    created = 0
    titles: list[str] = []
    for record in result.items[:MAX_ITEMS]:
        title = record.title.strip()[:300]
        if not title:
            continue
        if KnowledgeItem.objects.filter(title__iexact=title).exists():
            continue
        KnowledgeItem.objects.create(
            title=title,
            body=record.body.strip(),
            tags=[str(t).strip().lower() for t in record.tags[:6] if str(t).strip()],
            source="extraction",
            case=case,
            created_by=actor,
        )
        created += 1
        titles.append(title)

    if created:
        from apps.audit.models import record as audit_record

        case.events.create(kind="system", message=f"Extracted {created} knowledge item(s)", actor=actor)
        audit_record("create", obj=case, actor=actor, metadata={"knowledge_items": created, "titles": titles})
        logger.info("knowledge extraction case=%s created=%d", case.case_id, created)
    return {"created": created, "titles": titles}
