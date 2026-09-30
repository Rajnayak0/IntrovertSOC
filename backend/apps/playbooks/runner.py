"""Sequential playbook runner (ARCHITECTURE.md §6): plain Python, YAML steps,
no planning loop. Long runs execute in a background thread (MIGRATION #9 - no
Redis/workers); the UI polls GET /api/playbooks/runs/<id>/.

Allowed step types are an explicit whitelist - there is no other way to reach
the LLM from a playbook (MIGRATION #6: no custom code path to any model).
"""

from __future__ import annotations

import logging
import time

import yaml
from django.utils import timezone

from llm import local_engine
from llm.schemas import LLMError

from apps.agents.graphs import run_investigation
from apps.audit.models import record as audit_record
from apps.cases.context import format_case_context
from apps.enrichment import services as enrichment_services
from apps.knowledge import extraction

from .models import PlaybookRun

logger = logging.getLogger("apps.playbooks")

STEP_TYPES = {"log", "llm", "investigate", "extract_knowledge", "enrich"}


def _require_case(run: PlaybookRun) -> None:
    if run.case_id is None:
        raise ValueError("this step requires a case - run the playbook with case_id")


def _step_log(run: PlaybookRun, raw: dict, mode: str) -> str:
    return str(raw.get("message", ""))


def _step_llm(run: PlaybookRun, raw: dict, mode: str) -> str:
    _require_case(run)
    prompt = str(raw.get("prompt", "")).replace("{{case}}", format_case_context(run.case))
    answer = local_engine.complete(
        [{"role": "user", "content": prompt}],
        mode=mode,
        temperature=float(raw.get("temperature", 0.0)),
        max_tokens=int(raw.get("max_tokens", 700)),
    )
    text = answer.strip()
    return text[:600] + ("…" if len(text) > 600 else "")


def _step_investigate(run: PlaybookRun, raw: dict, mode: str) -> str:
    _require_case(run)
    outcome = run_investigation(case_pk=run.case_id, mode=mode, actor_id=run.created_by_id)
    degraded = outcome.get("degraded") or []
    return f"investigation complete ({outcome['ms']} ms)" + (f"; degraded: {', '.join(degraded)}" if degraded else "")


def _step_extract_knowledge(run: PlaybookRun, raw: dict, mode: str) -> str:
    _require_case(run)
    outcome = extraction.extract_for_case(run.case, actor=run.created_by)
    if outcome.get("skipped"):
        return f"skipped: {outcome['skipped']}"
    return f"created {outcome.get('created', 0)} knowledge item(s)"


def _step_enrich(run: PlaybookRun, raw: dict, mode: str) -> str:
    _require_case(run)
    outcome = enrichment_services.enrich_case(run.case)
    verdicts = [r["verdict"] for r in outcome["results"]]
    malicious = sum(1 for v in verdicts if v == "malicious")
    return f"{len(outcome['iocs'])} ioc(s), {len(verdicts)} result(s), {malicious} malicious"


STEP_HANDLERS = {
    "log": _step_log,
    "llm": _step_llm,
    "investigate": _step_investigate,
    "extract_knowledge": _step_extract_knowledge,
    "enrich": _step_enrich,
}


def execute_run(run: PlaybookRun, mode: str) -> None:
    """Run all steps sequentially; persists progress after every step (pollable)."""
    run.status = "running"
    run.mode = mode
    run.started_at = timezone.now()
    run.save(update_fields=["status", "mode", "started_at"])

    try:
        definition = yaml.safe_load(run.playbook.definition) or {}
        steps = definition.get("steps") or []
        if not isinstance(steps, list):
            raise ValueError("definition.steps must be a list")
    except (yaml.YAMLError, ValueError) as exc:
        run.status = "failed"
        run.error = f"invalid playbook definition: {exc}"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        return

    results: list[dict] = []
    had_error = False
    for index, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict) or raw.get("type") not in STEP_TYPES:
            results.append({"index": index, "type": str(raw), "status": "error",
                            "detail": f"unknown step type (allowed: {sorted(STEP_TYPES)})", "ms": 0})
            had_error = True
            run.steps = results
            run.save(update_fields=["steps"])
            continue

        handler = STEP_HANDLERS[raw["type"]]
        started = time.monotonic()
        try:
            detail = handler(run, raw, mode)
            status_name = "ok"
        except LLMError as exc:
            detail, status_name, had_error = f"model unavailable: {exc}", "error", True
        except ValueError as exc:
            detail, status_name, had_error = str(exc), "error", True
        except Exception as exc:  # step must never kill the run
            logger.exception("playbook run=%s step=%d crashed", run.pk, index)
            detail, status_name, had_error = f"{type(exc).__name__}: {exc}", "error", True
        results.append(
            {"index": index, "type": raw["type"], "status": status_name,
             "detail": detail[:800], "ms": int((time.monotonic() - started) * 1000)}
        )
        run.steps = results
        run.save(update_fields=["steps"])  # incremental: pollers see live progress

    run.status = "degraded" if had_error else "succeeded"
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "finished_at"])
    audit_record("update", obj=run, actor=run.created_by, metadata={"final_status": run.status})
    # (the spawning thread closes its own DB connection in views._spawn)
