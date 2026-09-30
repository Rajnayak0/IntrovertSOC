"""Playbook models: YAML definition + run history (ARCHITECTURE.md §6, §5)."""

from django.conf import settings
from django.db import models


class Playbook(models.Model):
    name = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True, default="")
    definition = models.TextField(help_text="YAML: steps list executed sequentially")
    enabled = models.BooleanField(default=True)
    builtin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "playbooks"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PlaybookRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("succeeded", "Succeeded"),
        ("degraded", "Degraded (some steps errored)"),
        ("failed", "Failed"),
    ]

    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE, related_name="runs")
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.SET_NULL, related_name="playbook_runs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="playbook_runs"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    mode = models.CharField(max_length=20, default="work", help_text="chat mode of the requester")
    steps = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "playbook_runs"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at", "-id"], name="pbrun_created_idx")]

    def __str__(self):
        return f"{self.playbook.name} #{self.pk} ({self.status})"
