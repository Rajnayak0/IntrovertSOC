"""ask_agent - interactive case Q&A. One short local_engine call, never a graph
(ARCHITECTURE.md section 6: interactive Q&A must stay snappy).

The caller's chat mode flows in via the endpoint (thread-local from middleware),
so the 3-way switch in the top nav changes every answer's verbosity.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from llm import adapter, chat_modes, local_engine

from apps.cases.context import format_case_context
from apps.knowledge.retrieval import context_block as kb_context_block

logger = logging.getLogger("apps.agents")

ASK_SYSTEM = (
    "You are an embedded SOC analyst assistant answering a question about ONE case. "
    "Use only the case context provided. Answer directly and concisely; if the context "
    "does not contain the answer, say exactly what is missing. No filler, no restating "
    "the question."
)

MAX_HISTORY = 8
HISTORY_MSG_CHARS = 1200
QUESTION_CHARS = 2000
CONTEXT_CHARS = 6000
INLINE_CONTEXT_CHARS = 120_000  # big-context models get case + full KB uncapped-ish


def ask_case(*, case, question: str, history: Sequence[dict], mode: str) -> dict[str, Any]:
    context = format_case_context(case)
    try:
        # Adaptive KB (Phase 10): whole KB inline when the model has >=128k context,
        # top-K keyword proposal otherwise.
        kb = kb_context_block(question, propose=True, body_chars=300)
    except Exception:
        logger.warning("kb retrieval failed", exc_info=True)
        kb = ""
    if kb:
        context += "\n\n" + kb
    cap = INLINE_CONTEXT_CHARS if adapter.wants_inline_kb() else CONTEXT_CHARS
    context = context[:cap]
    messages: list[dict[str, str]] = [
        {"role": "user", "content": f"Case context:\n{context}"},
    ]
    for turn in list(history)[-MAX_HISTORY:]:
        role = "assistant" if str(turn.get("role", "")).lower() == "assistant" else "user"
        content = str(turn.get("content", "") or "")[:HISTORY_MSG_CHARS]
        if content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question[:QUESTION_CHARS]})

    answer = local_engine.complete(
        messages,
        mode=mode,
        system=ASK_SYSTEM,
        temperature=0.2,
        max_tokens=chat_modes.budget(mode),  # Phase 10: mode-driven answer budget
    )
    return {"answer": answer.strip()}
