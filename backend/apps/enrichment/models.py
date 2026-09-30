"""Enrichment models: pluggable providers + per-IOC results (local feeds by default)."""

from django.db import models


class EnrichmentProvider(models.Model):
    KIND_CHOICES = [
        ("local_feed", "Local feed file (CSV)"),
        ("http_lookup", "HTTP lookup (user-owned endpoint)"),
    ]

    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="local_feed")
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enrichment_providers"

    def __str__(self):
        return f"{self.name} ({self.kind})"


class Enrichment(models.Model):
    VERDICTS = [
        ("malicious", "Malicious"),
        ("suspicious", "Suspicious"),
        ("clean", "Clean"),
        ("unknown", "Unknown"),
    ]

    ioc_value = models.CharField(max_length=255, db_index=True)
    ioc_type = models.CharField(max_length=20, default="other")
    provider = models.CharField(max_length=100)
    verdict = models.CharField(max_length=20, choices=VERDICTS, default="unknown")
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "enrichments"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["ioc_value", "provider"], name="uniq_enrichment_ioc_provider"),
        ]
        indexes = [models.Index(fields=["ioc_value", "-updated_at"], name="enrichment_ioc_idx")]

    def __str__(self):
        return f"{self.ioc_value} -> {self.verdict} ({self.provider})"
