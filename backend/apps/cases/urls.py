from django.urls import path

from apps.agents.views import case_ask, case_investigate
from apps.enrichment.views import case_enrich

from . import views

urlpatterns = [
    path("", views.case_list, name="case-list"),
    path("<int:pk>/", views.case_detail, name="case-detail"),
    path("<int:pk>/alerts/", views.case_link_alerts, name="case-link-alerts"),
    path("<int:pk>/investigate/", case_investigate, name="case-investigate"),
    path("<int:pk>/ask/", case_ask, name="case-ask"),
    path("<int:pk>/enrich/", case_enrich, name="case-enrich"),
]
