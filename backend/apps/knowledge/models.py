"""Knowledge base: reusable learnings extracted from closed cases (ARCHITECTURE.md §5).

Vector search is deferred (sqlite-vec is optional per §10): retrieval scores token
overlap over title/tags/body, with an LLM keyword-proposal step (MIGRATION #4)
and a deterministic regex-token fallback.
"""

from django.conf import settings
from django.db import models


class KnowledgeItem(models.Model):
    SOURCE_CHOICES = [
        ("extraction", "Extraction"),
        ("manual", "Manual"),
        ("playbook", "Playbook"),
    ]

    title = models.CharField(max_length=300)
    body = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="extraction")
    case = models.ForeignKey(
        "cases.Case", null=True, blank=True, on_delete=models.SET_NULL, related_name="knowledge_items"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="knowledge_items"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_items"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="kb_created_idx"),
            models.Index(fields=["source", "-created_at"], name="kb_source_idx"),
        ]

    def __str__(self):
        return self.title
