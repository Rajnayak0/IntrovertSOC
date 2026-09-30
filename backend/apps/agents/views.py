import time

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.cases.models import Case
from apps.cases.serializers import CaseSerializer
from apps.enrichment.services import enrich_case
from llm import local_engine
from llm.health import health_check, unavailable_banner
from llm.schemas import LLMError

from .ask import ask_case
from .graphs import run_investigation


def _model_down_response():
    health = health_check(force=True)
    if not health.ok:
        return Response({"detail": unavailable_banner(health)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return None


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def case_investigate(request, pk: int):
    """Synchronous investigation run (short nodes; Qwen3-class models finish in seconds).
    Model-down fails fast with the exact Model-Settings banner instead of degrading."""
    try:
        case = Case.objects.get(pk=pk)
    except Case.DoesNotExist:
        return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)

    down = _model_down_response()
    if down is not None:
        return down

    try:
        enrich_case(case)  # local feeds first, so the graph sees verdicts (best-effort)
    except Exception:
        import logging

        logging.getLogger("apps.agents").warning("pre-investigation enrichment failed", exc_info=True)

    started = time.monotonic()
    mode = local_engine.get_thread_mode()
    try:
        outcome = run_investigation(case_pk=case.pk, mode=mode, actor_id=request.user.id)
    except LLMError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    case.refresh_from_db()
    return Response(
        {
            "case": CaseSerializer(case, context={"detail": True}).data,
            "degraded": outcome["degraded"],
            "ms": int((time.monotonic() - started) * 1000),
            "mode": mode,
        }
    )


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def case_ask(request, pk: int):
    """ask_agent: one short mode-aware call per question (stateless history from client)."""
    try:
        case = Case.objects.get(pk=pk)
    except Case.DoesNotExist:
        return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)

    question = str(request.data.get("question", "") or "").strip()
    if not question:
        return Response({"detail": "question is required."}, status=status.HTTP_400_BAD_REQUEST)
    history = request.data.get("history") or []
    if not isinstance(history, list):
        return Response({"detail": "history must be a list of {role, content}."}, status=status.HTTP_400_BAD_REQUEST)

    down = _model_down_response()
    if down is not None:
        return down

    started = time.monotonic()
    mode = local_engine.get_thread_mode()
    try:
        out = ask_case(case=case, question=question, history=history, mode=mode)
    except LLMError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(
        {"answer": out["answer"], "mode": mode, "ms": int((time.monotonic() - started) * 1000)}
    )
