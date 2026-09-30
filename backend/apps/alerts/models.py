from django.db import models


class Severity(models.TextChoices):
    UNKNOWN = "Unknown"
    INFORMATIONAL = "Informational"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class AlertStatus(models.TextChoices):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    SUPPRESSED = "Suppressed"
    RESOLVED = "Resolved"


def normalize_choice(choice_cls, value, default):
    """Accept case-insensitive enum values ('critical' -> 'Critical')."""
    text = str(value or "").strip()
    for member in choice_cls:
        if text.lower() == member.value.lower():
            return member.value
    return default


def _next_alert_id() -> str:
    n = Alert.objects.count() + 1
    while Alert.objects.filter(alert_id=f"alert_{n:06d}").exists():
        n += 1
    return f"alert_{n:06d}"


class Alert(models.Model):
    """One alert from any source (manual entry, webhook batch, SIEM export).

    Leaner than the original (no disposition/analytic/policy product taxonomy):
    the fields IntrovertSOC actually consumes. Unmapped extras stay in raw_data.
    """

    alert_id = models.CharField(max_length=32, unique=True, editable=False, db_index=True, blank=True, default="")
    # Original had a required FK (alerts cannot exist unlinked); we allow orphan
    # alerts so ingestion works before a case exists -> set_null, not cascade.
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    title = models.CharField(max_length=500, blank=True, default="")
    desc = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=20, choices=Severity, default=Severity.UNKNOWN)
    status = models.CharField(max_length=20, choices=AlertStatus, default=AlertStatus.NEW)
    source = models.CharField(max_length=50, blank=True, default="manual")  # manual | webhook | siem | file
    source_uid = models.CharField(max_length=255, blank=True, default="", db_index=True)
    rule_id = models.CharField(max_length=255, blank=True, default="")
    rule_name = models.CharField(max_length=255, blank=True, default="")
    correlation_uid = models.CharField(max_length=255, blank=True, default="", db_index=True)
    tactic = models.CharField(max_length=100, blank=True, default="")
    technique = models.CharField(max_length=100, blank=True, default="")
    labels = models.JSONField(default=list, blank=True)
    iocs = models.JSONField(default=list, blank=True, help_text="regex-extracted [{type,value}] (deterministic)")
    first_seen = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.alert_id:
            self.alert_id = _next_alert_id()
        from apps.enrichment.iocs import extract_from_alert

        self.iocs = extract_from_alert(self)
        super().save(*args, **kwargs)

    class Meta:
        db_table = "alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="alert_created_idx"),
            models.Index(fields=["status", "-created_at"], name="alert_status_idx"),
            models.Index(fields=["severity", "-created_at"], name="alert_severity_idx"),
        ]

    def __str__(self):
        return self.title or self.alert_id
