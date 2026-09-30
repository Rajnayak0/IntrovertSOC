from django.db import models


class ModelConfig(models.Model):
    """DB override for the local LLM endpoint, edited from the Model Settings page.

    Blank fields fall back to .env (LLAMAFILE_*). There is deliberately NO api_key
    field - IntrovertSOC never stores or displays credentials for the model server.
    """

    base_url = models.URLField(max_length=300, blank=True, default="")
    model = models.CharField(max_length=200, blank=True, default="")
    gguf_path = models.CharField(max_length=1000, blank=True, default="")
    # Phase 10: 0 = auto (server-reported context length, else 32768 default).
    # Drives the adaptive KB strategy (>=128k => inline the whole knowledge base).
    context_window = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        verbose_name = "Model configuration"

    @classmethod
    def get_solo(cls) -> "ModelConfig | None":
        return cls.objects.order_by("pk").first()

    @classmethod
    def get_or_create_solo(cls) -> "ModelConfig":
        row = cls.get_solo()
        if row is None:
            row = cls.objects.create()
        return row
