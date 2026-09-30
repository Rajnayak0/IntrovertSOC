"""Knowledge base API: search/list, manual entries, extraction trigger."""

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.audit.models import record
from apps.cases.models import Case

from . import extraction
from .models import KnowledgeItem
from .retrieval import search as kb_search


def _item_dict(item: KnowledgeItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "tags": item.tags,
        "source": item.source,
        "case_id": item.case_id,
        "case": item.case.case_id if item.case else None,
        "created_at": item.created_at.isoformat(),
    }


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def knowledge_list(request):
    if request.method == "GET":
        q = str(request.query_params.get("q", "")).strip()
        limit = int(request.query_params.get("limit", 50))
        if q:
            hits = kb_search(q, top_k=limit, propose=True)
            return Response({"count": len(hits), "results": hits, "query": q})
        items = KnowledgeItem.objects.all()[:limit]
        results = [_item_dict(i) for i in items]
        return Response({"count": KnowledgeItem.objects.count(), "results": results})

    title = str(request.data.get("title", "")).strip()
    if not title:
        return Response({"detail": "title is required."}, status=status.HTTP_400_BAD_REQUEST)
    tags = request.data.get("tags") or []
    if not isinstance(tags, list):
        return Response({"detail": "tags must be a list."}, status=status.HTTP_400_BAD_REQUEST)
    item = KnowledgeItem.objects.create(
        title=title[:300],
        body=str(request.data.get("body", "") or ""),
        tags=[str(t).strip().lower() for t in tags[:6]],
        source="manual",
        created_by=request.user,
    )
    record("create", obj=item, actor=request.user, metadata={"title": item.title})
    return Response(_item_dict(item), status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def knowledge_detail(request, pk: int):
    try:
        item = KnowledgeItem.objects.get(pk=pk)
    except KnowledgeItem.DoesNotExist:
        return Response({"detail": "Knowledge item not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        title = item.title
        item.delete()
        record("delete", obj=None, actor=request.user, metadata={"knowledge_title": title})
        return Response({"detail": f"{title} deleted."})
    return Response(_item_dict(item))


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsEditor])
def knowledge_extract(request):
    """POST {"case_id": 1} -> run extraction now (also fires automatically on close)."""
    case_id = request.data.get("case_id")
    try:
        case = Case.objects.get(pk=case_id)
    except (Case.DoesNotExist, ValueError, TypeError):
        return Response({"detail": "Case not found."}, status=status.HTTP_404_NOT_FOUND)
    outcome = extraction.extract_for_case(case, actor=request.user)
    return Response({"case": case.case_id, **outcome})
