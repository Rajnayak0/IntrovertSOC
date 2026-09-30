"""Investigation graph - short LangGraph nodes, one local_engine call each.

Flow (ARCHITECTURE.md section 6):
  load_context -> summarize -> assess (JSON) -> report -> persist

Degraded-mode rule: any LLM node that fails falls back to a deterministic default
and records itself in state["degraded"]; runs never hard-fail. The API endpoint
checks model health first, so "server down" surfaces as a clear503 banner instead.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from llm import chat_modes, local_engine
from llm.schemas import LLMError

logger = logging.getLogger("apps.agents")

SUMMARIZE_SYSTEM = (
    "You are a SOC case summarizer. Write a factual 5-8 line summary of the case from the "
    "provided context only. No speculation, plain markdown, no preamble."
)

ASSESS_SYSTEM = (
    "You are a SOC severity assessor. Assess the case from the provided context only. "
    'Respond with ONLY a JSON object: {"severity": "Critical|High|Medium|Low|Informational|Unknown", '
    '"confidence": "high|medium|low", "verdict": "True Positive|False Positive|Suspicious|Benign|'
    'Insufficient Data|Unknown", "rationale": "...", "next_steps": ["...", "..."]}'
)

REPORT_SYSTEM = (
    "You are a SOC investigator. Write a markdown investigation report with sections: "
    "## Summary, ## Evidence, ## Assessment, ## Recommended actions. Use only the provided "
    "context; if data is missing, say so."
)


class Assessment(BaseModel):
    severity: str
    confidence: str
    verdict: str
    rationale: str
    next_steps: list[str] = []


class InvestigationState(TypedDict, total=False):
    case_pk: int
    actor_id: int | None
    mode: str
    context: str
    case: dict[str, Any]
    summary: str
    assessment: dict[str, Any]
    report_md: str
    degraded: list[str]


# --------------------------------------------------------------------------- nodes
from apps.cases.context import format_case_context  # re-exported for ask/playbooks


def _load_context(state: InvestigationState) -> dict:
    """Pure Python: case + alerts + events + KB (adaptive: full inline on big ctx, else top-3)."""
    from apps.cases.models import Case
    from apps.knowledge.retrieval import context_block as kb_context_block

    case = Case.objects.prefetch_related("alerts").get(pk=state["case_pk"])
    query = f"{case.title} {' '.join(case.tags)} {case.description[:300]}"
    context = format_case_context(case)
    kb = kb_context_block(query, propose=False, body_chars=400)
    if kb:
        context += "\n\n" + kb
    return {
        "context": context,
        "case": {
            "case_id": case.case_id,
            "title": case.title,
            "severity": case.severity,
            "status": case.status,
        },
    }


def _summarize(state: InvestigationState) -> dict:
    """One short call:5-8 line summary (fixed pipeline shape -> mode=work)."""
    try:
        text = local_engine.complete(
            [local_engine.user(state["context"])],
            mode="work",
            system=SUMMARIZE_SYSTEM,
            temperature=0.2,
            max_tokens=600,
        )
        return {"summary": text.strip()}
    except LLMError as exc:
        logger.warning("investigate summarize degraded: %s", exc)
        return {"summary": "", "degraded": [*state.get("degraded", []), "summarize"]}


def _assess(state: InvestigationState) -> dict:
    """One JSON call: severity/confidence/verdict/rationale/next_steps."""
    prompt = f"{state['context']}\n\nSummary:\n{state.get('summary') or '(no summary available)'}"
    try:
        result = local_engine.complete_json(
            [local_engine.user(prompt)],
            schema=Assessment,
            mode="work",
            system=ASSESS_SYSTEM,
            temperature=0.0,
            max_tokens=800,
        )
        return {"assessment": result.model_dump()}
    except LLMError as exc:
        logger.warning("investigate assess degraded: %s", exc)
        case = state.get("case") or {}
        return {
            "assessment": {
                "severity": case.get("severity") or "Unknown",
                "confidence": "low",
                "verdict": "Insufficient Data",
                "rationale": f"Model output unusable ({exc}); defaulted from case fields.",
                "next_steps": [],
            },
            "degraded": [*state.get("degraded", []), "assess"],
        }


def _report(state: InvestigationState) -> dict:
    """One call: markdown report - the mode-aware node (caller's verbosity)."""
    prompt = (
        f"Context:\n{state['context']}\n\n"
        f"Summary:\n{state.get('summary') or '(no summary available)'}\n\n"
        f"Assessment JSON:\n{json.dumps(state.get('assessment') or {}, indent=2)}"
    )
    try:
        text = local_engine.complete(
            [local_engine.user(prompt)],
            mode=state.get("mode"),
            system=REPORT_SYSTEM,
            temperature=0.3,
            # Phase 10: answer length follows the selected mode's budget
            max_tokens=chat_modes.budget(state.get("mode")),
        )
        return {"report_md": text.strip()}
    except LLMError as exc:
        logger.warning("investigate report degraded: %s", exc)
        return {
            "report_md": f"partial - model output unusable. Raw failure: {exc}",
            "degraded": [*state.get("degraded", []), "report"],
        }


def _persist(state: InvestigationState) -> dict:
    """Pure Python: write AI fields, report JSON, timeline event, audit entry."""
    from apps.accounts.models import User
    from apps.audit.models import record
    from apps.cases.models import Case, CaseEvent
    from llm import chat_modes
    from llm.config import get_endpoint_config

    case = Case.objects.get(pk=state["case_pk"])
    assessment = state.get("assessment") or {}
    degraded = state.get("degraded", [])
    mode = chat_modes.normalize_mode(state.get("mode"))

    case.severity_ai = str(assessment.get("severity") or "")[:20] or "Unknown"
    case.confidence_ai = str(assessment.get("confidence") or "")
    case.verdict_ai = str(assessment.get("verdict") or "")[:30]
    case.investigation_report_ai_json = json.dumps(
        {
            "summary": state.get("summary", ""),
            "assessment": assessment,
            "report_md": state.get("report_md", ""),
            "mode": mode,
            "model": get_endpoint_config().model,
            "degraded": degraded,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    case.save(
        update_fields=[
            "severity_ai", "confidence_ai", "verdict_ai",
            "investigation_report_ai_json", "updated_at",
        ]
    )

    msg = f"AI investigation completed (mode={mode})"
    if degraded:
        msg += f" [degraded: {', '.join(degraded)}]"
    CaseEvent.objects.create(case=case, kind="system", message=msg, data={"degraded": degraded})

    actor = None
    if state.get("actor_id"):
        actor = User.objects.filter(pk=state["actor_id"]).first()
    record(
        "update",
        obj=case,
        actor=actor,
        changes={"ai_investigation": {"severity_ai": case.severity_ai, "verdict_ai": case.verdict_ai}},
        metadata={"mode": mode, "degraded": degraded},
    )
    return {}


def build_investigation_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("load_context", _load_context)
    graph.add_node("summarize", _summarize)
    graph.add_node("assess", _assess)
    graph.add_node("report", _report)
    graph.add_node("persist", _persist)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "summarize")
    graph.add_edge("summarize", "assess")
    graph.add_edge("assess", "report")
    graph.add_edge("report", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


def run_investigation(case_pk: int, mode: str, actor_id: int | None) -> dict:
    """Service entry point - also the hook Playbooks call (MIGRATION #7, runner in Phase 7)."""
    started = time.monotonic()
    result = build_investigation_graph().invoke(
        {"case_pk": case_pk, "mode": mode, "actor_id": actor_id, "degraded": []}
    )
    return {
        "degraded": result.get("degraded", []),
        "ms": int((time.monotonic() - started) * 1000),
    }
