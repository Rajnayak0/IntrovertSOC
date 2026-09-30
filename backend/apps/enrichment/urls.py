from django.urls import path

from . import views

urlpatterns = [
    path("", views.enrichment_list, name="enrichment-list"),
    path("providers/", views.provider_list, name="enrichment-providers"),
    path("providers/<int:pk>/", views.provider_detail, name="enrichment-provider-detail"),
]
