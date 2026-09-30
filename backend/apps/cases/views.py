from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.alerts.models import Alert
from apps.audit.models import record

from .models import Case, CaseEvent, CaseStatus
from .serializers import CaseSerializer


def _filter(queryset, params):
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if params.get("severity"):
        queryset = queryset.filter(severity=params["severity"])
    if params.get("assignee"):
        queryset = queryset.filter(assignee__username=params["assignee"])
    q = params.get("q")
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(case_id__icontains=q)
        )
    return queryset


def _timeline(case: Case, kind: str, message: str, actor=None, data: dict | None = None):
    CaseEvent.objects.create(case=case, kind=kind, message=message, actor=actor, data=data or {})


def _base_qs():
    return Case.objects.select_related("assignee").annotate(alert_count=Count("alerts", distinct=True))


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def case_list(request):
    if request.method == "GET":
        qs = _filter(_base_qs(), request.query_params)
        limit = int(request.query_params.get("limit", 50))
        serializer = CaseSerializer(qs[:limit], many=True, context={"detail": False})
        return Response({"count": qs.count(), "results": serializer.data})

    serializer = CaseSerializer(data={**request.data, "alert_count": 0})
    serializer.is_valid(raise_exception=True)
    case = serializer.save()
    _timeline(case, "system", "Case created", actor=request.user)
    record("create", obj=case, actor=request.user, metadata={"title": case.title})
    return Response(CaseSerializer(case, context={"detail": True}).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def case_detail(request, pk: int):
    try:
        case = _base_qs().get(pk=pk)
    except Case.DoesNotExist:
        return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CaseSerializer(case, context={"detail": True}).data)

    if request.method == "DELETE":
        case_id = case.case_id
        case.delete()
        record("delete", obj=None, actor=request.user, metadata={"case_id": case_id})
        return Response({"detail": f"{case_id} deleted."})

    changes = {}
    for field in ("title", "severity", "priority", "status", "verdict", "assignee", "description", "summary"):
        if field in request.data:
            old = getattr(case, field)
            if str(old) != str(request.data[field]):
                changes[field] = {"old": str(old), "new": str(request.data[field])}

    serializer = CaseSerializer(case, data=request.data, partial=True, context={"detail": False})
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()

    if "status" in changes:
        _timeline(
            updated, "status",
            f"Status: {changes['status']['old'] or 'unset'} → {changes['status']['new']}",
            actor=request.user,
        )
        if updated.status in (CaseStatus.RESOLVED, CaseStatus.CLOSED) and not updated.closed_time:
            updated.closed_time = timezone.now()
            updated.save(update_fields=["closed_time", "updated_at"])
        if updated.status == CaseStatus.CLOSED:
            from apps.knowledge import extraction

            extraction.extract_for_case(updated, actor=request.user)
    if changes:
        record("update", obj=updated, actor=request.user, changes=changes)
    return Response(CaseSerializer(updated, context={"detail": True}).data)


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def case_link_alerts(request, pk: int):
    """POST {"alert_ids": [3, 7]} -> attach alerts to this case (correlation step)."""
    try:
        case = Case.objects.get(pk=pk)
    except Case.DoesNotExist:
        return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)

    alert_ids = request.data.get("alert_ids")
    if not isinstance(alert_ids, list) or not alert_ids:
        return Response({"detail": "alert_ids must be a non-empty list."}, status=status.HTTP_400_BAD_REQUEST)

    alerts = Alert.objects.filter(pk__in=alert_ids)
    missing = set(alert_ids) - {a.pk for a in alerts}
    if missing:
        return Response({"detail": f"Unknown alert ids: {sorted(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

    linked = 0
    for alert in alerts:
        if alert.case_id != case.pk:
            alert.case = case
            alert.save(update_fields=["case", "updated_at"])
            linked += 1
    if linked:
        _timeline(case, "link", f"Linked {linked} alert(s)", actor=request.user,
                  data={"alert_ids": [a.alert_id for a in alerts]})
        record("update", obj=case, actor=request.user, metadata={"linked_alerts": linked})
    return Response({"linked": linked, "total": len(alerts)})
