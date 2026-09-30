from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.audit.models import record

from .models import Alert
from .serializers import AlertSerializer


def _filter(queryset, params):
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if params.get("severity"):
        queryset = queryset.filter(severity=params["severity"])
    if params.get("correlation_uid"):
        queryset = queryset.filter(correlation_uid=params["correlation_uid"])
    if params.get("case"):
        queryset = queryset.filter(case_id=params["case"])
    if params.get("source"):
        queryset = queryset.filter(source=params["source"])
    if str(params.get("orphan", "")).lower() in {"1", "true", "yes"}:
        queryset = queryset.filter(case__isnull=True)
    q = params.get("q")
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(desc__icontains=q) | Q(alert_id__icontains=q))
    return queryset


def _create_one(data: dict, source: str) -> Alert:
    if not isinstance(data, dict):
        raise ValueError("each alert must be a JSON object")
    payload = dict(data)
    if not payload.get("title"):
        payload["title"] = "Untitled alert"
    payload.setdefault("source", source)
    serializer = AlertSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def alert_list(request):
    """GET: filtered alert list. POST: one alert, or a batch via {"alerts": [...]}."""
    if request.method == "GET":
        qs = _filter(Alert.objects.all(), request.query_params)
        page = qs[: int(request.query_params.get("limit", 50))]
        serializer = AlertSerializer(page, many=True)
        return Response({"count": qs.count(), "results": serializer.data})

    raw = request.data.get("alerts") if isinstance(request.data, dict) and "alerts" in request.data else request.data
    items = raw if isinstance(raw, list) else [raw]
    if not items:
        return Response({"detail": "No alerts in payload."}, status=status.HTTP_400_BAD_REQUEST)

    source = str(request.data.get("source", "webhook") if isinstance(request.data, dict) else "webhook") or "webhook"
    created = []
    errors = []
    for idx, item in enumerate(items):
        try:
            created.append(_create_one(item, source))
        except Exception as exc:  # keep batch partially successful, report bad rows
            errors.append({"index": idx, "detail": str(exc)})

    if created:
        record(
            "ingest",
            obj=None,
            actor=request.user if request.user.is_authenticated else None,
            metadata={"count": len(created), "source": source, "errors": len(errors)},
        )

    if not isinstance(raw, list):
        if errors:
            return Response({"detail": errors[0]["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AlertSerializer(created[0]).data, status=status.HTTP_201_CREATED)

    return Response(
        {"created": len(created), "errors": errors, "alert_ids": [a.alert_id for a in created]},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def alert_detail(request, pk: int):
    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(AlertSerializer(alert).data)

    changes = {}
    for field in ("title", "severity", "status", "desc", "labels", "case", "correlation_uid"):
        if field in request.data:
            old = getattr(alert, field)
            if str(old) != str(request.data[field]):
                changes[field] = {"old": str(old), "new": str(request.data[field])}
    serializer = AlertSerializer(alert, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()
    if changes:
        record("update", obj=updated, actor=request.user, changes=changes)
    return Response(AlertSerializer(updated).data)
