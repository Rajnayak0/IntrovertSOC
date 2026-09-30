from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole

from .models import AuditLog


def _row(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "action": log.action,
        "actor": log.actor.username if log.actor_id else None,
        "object": f"{log.content_type.model}.{log.object_id}" if log.content_type_id else None,
        "changes": log.changes,
        "metadata": log.metadata,
        "created_at": log.created_at.isoformat(),
    }


@api_view(["GET"])
@permission_classes([IsAdminRole])
def audit_list(request):
    qs = AuditLog.objects.select_related("actor", "content_type")
    if request.query_params.get("action"):
        qs = qs.filter(action=request.query_params["action"])
    if request.query_params.get("actor"):
        qs = qs.filter(actor__username=request.query_params["actor"])
    limit = int(request.query_params.get("limit", 50))
    rows = qs[:limit]
    return Response({"count": qs.count(), "results": [_row(r) for r in rows]})
