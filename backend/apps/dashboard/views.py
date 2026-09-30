from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.alerts.models import Alert
from apps.cases.models import Case, CaseStatus

OPEN_STATUSES = [s for s in CaseStatus if s not in (CaseStatus.RESOLVED, CaseStatus.CLOSED)]


def _counts(qs, field: str) -> dict:
    rows = qs.values(field).annotate(n=Count("id"))
    return {str(r[field] or ""): r["n"] for r in rows}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """One round-trip payload for the Dashboard page (no LLM involved)."""
    now = timezone.now()
    day_ago = now - timezone.timedelta(hours=24)

    recent_alerts = list(
        Alert.objects.order_by("-created_at").values(
            "id", "alert_id", "title", "severity", "status", "correlation_uid", "created_at"
        )[:8]
    )
    for row in recent_alerts:
        row["created_at"] = row["created_at"].isoformat()

    recent_cases = list(
        Case.objects.annotate(n=Count("alerts"))
        .order_by("-created_at")
        .values("id", "case_id", "title", "severity", "status", "n", "created_at")[:8]
    )
    for row in recent_cases:
        row["created_at"] = row["created_at"].isoformat()
        row["alert_count"] = row.pop("n")

    return Response(
        {
            "alerts": {
                "total": Alert.objects.count(),
                "last_24h": Alert.objects.filter(created_at__gte=day_ago).count(),
                "unassigned": Alert.objects.filter(case__isnull=True).count(),
                "by_severity": _counts(Alert.objects.all(), "severity"),
                "by_status": _counts(Alert.objects.all(), "status"),
            },
            "cases": {
                "total": Case.objects.count(),
                "open": Case.objects.filter(status__in=OPEN_STATUSES).count(),
                "by_status": _counts(Case.objects.all(), "status"),
            },
            "recent_alerts": recent_alerts,
            "recent_cases": recent_cases,
        }
    )
