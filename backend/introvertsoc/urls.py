from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """App liveness (does not touch the LLM server)."""
    return JsonResponse({"status": "ok", "app": "introvertsoc"})


urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/model/", include("apps.modelconfig.urls")),
    path("api/alerts/", include("apps.alerts.urls")),
    path("api/cases/", include("apps.cases.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/knowledge/", include("apps.knowledge.urls")),
    path("api/enrichment/", include("apps.enrichment.urls")),
    path("api/playbooks/", include("apps.playbooks.urls")),
]
