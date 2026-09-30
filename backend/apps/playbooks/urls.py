from django.urls import path

from . import views

urlpatterns = [
    path("", views.playbook_list, name="playbook-list"),
    path("runs/", views.run_list, name="playbook-runs"),
    path("runs/<int:pk>/", views.run_detail, name="playbook-run-detail"),
    path("<int:pk>/run/", views.playbook_run, name="playbook-run"),
    path("<int:pk>/", views.playbook_detail, name="playbook-detail"),
]
