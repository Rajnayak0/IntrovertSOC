from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.model_status, name="model-status"),
    path("test/", views.model_test, name="model-test"),
    path("config/", views.model_config_detail, name="model-config"),
]
