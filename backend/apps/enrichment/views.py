"""Enrichment API: on-demand case enrichment, results query, provider management."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole, IsEditor
from apps.audit.models import record
from apps.cases.models import Case

from .models import Enrichment, EnrichmentProvider
from .services import ensure_default_provider, enrich_case


def _provider_dict(p: EnrichmentProvider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "kind": p.kind,
        "config": p.config,
        "enabled": p.enabled,
        "created_at": p.created_at.isoformat(),
    }


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def case_enrich(request, pk: int):
    """POST -> extract IOCs from linked alerts and run all enabled providers."""
    try:
        case = Case.objects.get(pk=pk)
    except Case.DoesNotExist:
        return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)
    outcome = enrich_case(case)
    if outcome["iocs"]:
        record("update", obj=case, actor=request.user, metadata={"enriched_iocs": len(outcome["iocs"])})
    return Response({"case": case.case_id, **outcome})


@api_view(["GET"])
def enrichment_list(request):
    q = str(request.query_params.get("q", "")).strip()
    limit = int(request.query_params.get("limit", 50))
    qs = Enrichment.objects.all()
    if q:
        qs = qs.filter(Q(ioc_value__icontains=q) | Q(provider__icontains=q))
    results = [
        {
            "ioc_value": r.ioc_value,
            "ioc_type": r.ioc_type,
            "provider": r.provider,
            "verdict": r.verdict,
            "data": r.data,
            "updated_at": r.updated_at.isoformat(),
        }
        for r in qs[:limit]
    ]
    return Response({"count": len(results), "results": results})


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
def provider_list(request):
    if request.method == "GET":
        ensure_default_provider()
        return Response({"results": [_provider_dict(p) for p in EnrichmentProvider.objects.order_by("name")]})

    if not request.user.is_admin_role:
        return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)
    name = str(request.data.get("name", "")).strip()
    kind = str(request.data.get("kind", "")).strip()
    if not name or kind not in {"local_feed", "http_lookup"}:
        return Response({"detail": "name and a valid kind are required."}, status=status.HTTP_400_BAD_REQUEST)
    if kind == "local_feed":
        path = str(request.data.get("config", {}).get("path", "") or "")
        if not path:
            return Response({"detail": "local_feed requires config.path."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        template = str(request.data.get("config", {}).get("url_template", "") or "")
        if "{value}" not in template:
            return Response({"detail": "http_lookup requires config.url_template with {value}."},
                            status=status.HTTP_400_BAD_REQUEST)
    if EnrichmentProvider.objects.filter(name=name).exists():
        return Response({"detail": "Provider name already exists."}, status=status.HTTP_400_BAD_REQUEST)
    provider = EnrichmentProvider.objects.create(
        name=name[:100], kind=kind, config=request.data.get("config") or {},
        enabled=bool(request.data.get("enabled", True)),
    )
    record("create", obj=provider, actor=request.user, metadata={"name": provider.name, "kind": kind})
    return Response(_provider_dict(provider), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@parser_classes([JSONParser])
@permission_classes([IsAdminRole])
def provider_detail(request, pk: int):
    try:
        provider = EnrichmentProvider.objects.get(pk=pk)
    except EnrichmentProvider.DoesNotExist:
        return Response({"detail": "Provider not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        name = provider.name
        provider.delete()
        record("delete", obj=None, actor=request.user, metadata={"provider": name})
        return Response({"detail": f"{name} deleted."})
    for field in ("name", "config", "enabled", "kind"):
        if field in request.data:
            setattr(provider, field, request.data[field])
    try:
        provider.full_clean()
    except DjangoValidationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    provider.save()
    record("update", obj=provider, actor=request.user, metadata={"name": provider.name})
    return Response(_provider_dict(provider))
