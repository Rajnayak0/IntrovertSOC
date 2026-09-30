from django.apps import AppConfig


class ModelconfigConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.modelconfig"
    verbose_name = "Model Settings"
