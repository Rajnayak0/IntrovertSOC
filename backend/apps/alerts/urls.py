from django.urls import path

from . import views

urlpatterns = [
    path("", views.alert_list, name="alert-list"),
    path("<int:pk>/", views.alert_detail, name="alert-detail"),
]
