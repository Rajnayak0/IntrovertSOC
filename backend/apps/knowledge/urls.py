from django.urls import path

from . import views

urlpatterns = [
    path("", views.knowledge_list, name="knowledge-list"),
    path("extract/", views.knowledge_extract, name="knowledge-extract"),
    path("<int:pk>/", views.knowledge_detail, name="knowledge-detail"),
]
