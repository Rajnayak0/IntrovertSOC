from django.conf import settings
from django.db import models

from apps.alerts.models import Severity


class CaseStatus(models.TextChoices):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    ON_HOLD = "On Hold"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class CaseVerdict(models.TextChoices):
    UNKNOWN = "Unknown"
    FALSE_POSITIVE = "False Positive"
    TRUE_POSITIVE = "True Positive"
    SUSPICIOUS = "Suspicious"
    BENIGN = "Benign"
    INSUFFICIENT_DATA = "Insufficient Data"


def _next_case_id() -> str:
    n = Case.objects.count() + 1
    while Case.objects.filter(case_id=f"case_{n:06d}").exists():
        n += 1
    return f"case_{n:06d}"


class Case(models.Model):
    """An investigation case. AI assessment fields pre-declared for Phase 5
    (agent investigation writes *_ai and investigation_report_ai_json)."""

    case_id = models.CharField(max_length=32, unique=True, editable=False, db_index=True, blank=True, default="")
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=20, choices=Severity, blank=True, default="")
    priority = models.CharField(max_length=20, choices=Severity, blank=True, default="")
    status = models.CharField(max_length=20, choices=CaseStatus, default=CaseStatus.NEW)
    verdict = models.CharField(max_length=30, choices=CaseVerdict, blank=True, default="")
    summary = models.TextField(blank=True, default="", help_text="Closure / investigation summary")
    tags = models.JSONField(default=list, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_cases"
    )
    correlation_uid = models.CharField(max_length=255, blank=True, default="", db_index=True)
    closed_time = models.DateTimeField(null=True, blank=True)

    # AI fields (Phase 5 fills these from the investigation graph)
    severity_ai = models.CharField(max_length=20, choices=Severity, blank=True, default="")
    confidence_ai = models.CharField(max_length=20, blank=True, default="")
    priority_ai = models.CharField(max_length=20, choices=Severity, blank=True, default="")
    verdict_ai = models.CharField(max_length=30, choices=CaseVerdict, blank=True, default="")
    investigation_report_ai_json = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.case_id:
            self.case_id = _next_case_id()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "cases"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="case_created_idx"),
            models.Index(fields=["status", "-created_at"], name="case_status_idx"),
            models.Index(fields=["severity", "-created_at"], name="case_severity_idx"),
        ]

    def __str__(self):
        return self.title or self.case_id


class CaseEvent(models.Model):
    """Append-only timeline entry shown on the case detail page."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=20, choices=[
        ("comment", "Comment"),
        ("status", "Status change"),
        ("link", "Alert link"),
        ("system", "System"),
    ])
    message = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="case_events"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "case_events"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["case", "created_at"], name="case_event_idx")]

    def __str__(self):
        return f"{self.case.case_id}: {self.kind} {self.message[:40]}"
