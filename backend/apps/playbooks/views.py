"""Playbook API: list/CRUD definitions, trigger runs (thread + polling), run status."""

import threading

import yaml
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole, IsEditor
from apps.audit.models import record
from llm import local_engine

from .builtins import sync_builtins
from .models import Playbook, PlaybookRun
from .runner import STEP_TYPES, execute_run


def _playbook_dict(pb: Playbook) -> dict:
    return {
        "id": pb.id,
        "name": pb.name,
        "description": pb.description,
        "definition": pb.definition,
        "enabled": pb.enabled,
        "builtin": pb.builtin,
        "steps_preview": _step_types(pb.definition),
        "updated_at": pb.updated_at.isoformat(),
    }


def _step_types(definition: str) -> list[str]:
    try:
        data = yaml.safe_load(definition) or {}
        return [str(s.get("type")) for s in data.get("steps") or [] if isinstance(s, dict)]
    except yaml.YAMLError:
        return []


def _run_dict(run: PlaybookRun) -> dict:
    return {
        "id": run.id,
        "playbook_id": run.playbook_id,
        "playbook": run.playbook.name,
        "case_id": run.case_id,
        "case": run.case.case_id if run.case_id else None,
        "status": run.status,
        "mode": run.mode,
        "steps": run.steps,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "created_at": run.created_at.isoformat(),
        "created_by": run.created_by.username if run.created_by_id else None,
    }


def _spawn(run: PlaybookRun, mode: str) -> None:
    def _target():
        try:
            execute_run(run, mode)
        finally:
            from django.db import connection

            connection.close()

    threading.Thread(target=_target, name=f"playbook-run-{run.pk}", daemon=True).start()


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
def playbook_list(request):
    if request.method == "GET":
        if not Playbook.objects.exists():
            sync_builtins()
        return Response({"results": [_playbook_dict(pb) for pb in Playbook.objects.all()]})

    if not request.user.is_admin_role:
        return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)
    name = str(request.data.get("name", "")).strip()
    definition = str(request.data.get("definition", "") or "")
    if not name or not definition:
        return Response({"detail": "name and definition are required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        data = yaml.safe_load(definition) or {}
    except yaml.YAMLError as exc:
        return Response({"detail": f"invalid YAML: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list) or not steps:
        return Response({"detail": "definition must contain a non-empty steps list."},
                        status=status.HTTP_400_BAD_REQUEST)
    unknown = [s.get("type") for s in steps if isinstance(s, dict) and s.get("type") not in STEP_TYPES]
    if unknown:
        return Response({"detail": f"unknown step types: {unknown}; allowed: {sorted(STEP_TYPES)}"},
                        status=status.HTTP_400_BAD_REQUEST)
    if Playbook.objects.filter(name=name).exists():
        return Response({"detail": "Playbook name already exists."}, status=status.HTTP_400_BAD_REQUEST)
    pb = Playbook.objects.create(
        name=name[:80],
        description=str(request.data.get("description", "") or ""),
        definition=definition,
        enabled=bool(request.data.get("enabled", True)),
    )
    record("create", obj=pb, actor=request.user, metadata={"name": pb.name})
    return Response(_playbook_dict(pb), status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@parser_classes([JSONParser])
def playbook_detail(request, pk: int):
    try:
        pb = Playbook.objects.get(pk=pk)
    except Playbook.DoesNotExist:
        return Response({"detail": "Playbook not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(_playbook_dict(pb))
    if not request.user.is_admin_role:
        return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "DELETE":
        name = pb.name
        pb.delete()
        record("delete", obj=None, actor=request.user, metadata={"playbook": name})
        return Response({"detail": f"{name} deleted."})

    changes = {}
    for field in ("description", "definition", "enabled"):
        if field in request.data and str(getattr(pb, field)) != str(request.data[field]):
            changes[field] = True
            setattr(pb, field, request.data[field])
    if "definition" in changes:
        try:
            data = yaml.safe_load(pb.definition) or {}
        except yaml.YAMLError as exc:
            return Response({"detail": f"invalid YAML: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
        steps = data.get("steps") if isinstance(data, dict) else None
        if not isinstance(steps, list) or not steps:
            return Response({"detail": "definition must contain a non-empty steps list."},
                            status=status.HTTP_400_BAD_REQUEST)
    pb.save()
    if changes:
        record("update", obj=pb, actor=request.user, metadata={"name": pb.name})
    return Response(_playbook_dict(pb))


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def playbook_run(request, pk: int):
    """Start a run: short ones inline (PLAYBOOKS_SYNC, tests), else background thread."""
    try:
        pb = Playbook.objects.get(pk=pk)
    except Playbook.DoesNotExist:
        return Response({"detail": "Playbook not found."}, status=status.HTTP_404_NOT_FOUND)
    if not pb.enabled:
        return Response({"detail": "Playbook is disabled."}, status=status.HTTP_400_BAD_REQUEST)

    case = None
    case_id = request.data.get("case_id")
    if case_id not in (None, ""):
        from apps.cases.models import Case

        try:
            case = Case.objects.get(pk=case_id)
        except (Case.DoesNotExist, ValueError):
            return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)

    mode = local_engine.get_thread_mode()
    run = PlaybookRun.objects.create(playbook=pb, case=case, created_by=request.user, mode=mode)
    record("create", obj=run, actor=request.user, metadata={"playbook": pb.name, "case": getattr(case, "case_id", None)})

    if getattr(settings, "PLAYBOOKS_SYNC", False):
        execute_run(run, mode)
    else:
        _spawn(run, mode)
    return Response(_run_dict(run), status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
def run_list(request):
    limit = int(request.query_params.get("limit", 20))
    qs = PlaybookRun.objects.select_related("playbook", "case", "created_by")
    if request.query_params.get("playbook"):
        qs = qs.filter(playbook__name=request.query_params["playbook"])
    if request.query_params.get("case"):
        qs = qs.filter(case__pk=request.query_params["case"])
    results = [_run_dict(r) for r in qs[:limit]]
    return Response({"count": len(results), "results": results})


@api_view(["GET"])
def run_detail(request, pk: int):
    try:
        run = PlaybookRun.objects.select_related("playbook", "case", "created_by").get(pk=pk)
    except PlaybookRun.DoesNotExist:
        return Response({"detail": "Run not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(_run_dict(run))
