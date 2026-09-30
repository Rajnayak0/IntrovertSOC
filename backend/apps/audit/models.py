"""Local audit trail: logins, config edits, case/alert changes.

Leaner than the original: same generic-object shape, but content_type is nullable
so auth events (login/logout, no object) can be recorded too. Stored only in SQLite.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    action = models.CharField(max_length=20)  # login/logout/create/update/delete/ingest
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="audit_time_idx"),
            models.Index(fields=["actor", "-created_at"], name="audit_actor_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_idx"),
        ]

    def __str__(self):
        who = self.actor.username if self.actor_id else "system"
        return f"{self.action} by {who}"


def record(action: str, obj=None, actor=None, changes: dict | None = None, metadata: dict | None = None) -> AuditLog:
    content_type = None
    object_id = ""
    if obj is not None:
        content_type = ContentType.objects.get_for_model(type(obj))
        object_id = str(getattr(obj, "pk", ""))
    return AuditLog.objects.create(
        action=action,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        content_type=content_type,
        object_id=object_id,
        changes=changes or {},
        metadata=metadata or {},
    )
