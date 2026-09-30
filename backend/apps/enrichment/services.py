"""Enrichment services: run providers over IOC values, per-case convenience."""

from __future__ import annotations

import logging

from .iocs import classify
from .models import Enrichment, EnrichmentProvider
from .providers import REGISTRY, ProviderLookupError

logger = logging.getLogger("apps.enrichment")


def ensure_default_provider() -> EnrichmentProvider:
    """Seed the shipped local feed once (used by the providers list endpoint)."""
    from django.conf import settings

    provider, created = EnrichmentProvider.objects.get_or_create(
        name="local_reputation",
        defaults={
            "kind": "local_feed",
            "config": {"path": str(settings.BASE_DIR / "data" / "threat_feeds" / "local_reputation.csv")},
        },
    )
    return provider


def enrich_values(values: list[str], *, refresh: bool = True) -> list[Enrichment]:
    """Run every enabled provider over each value; persist hits (update_or_create)."""
    rows: list[Enrichment] = []
    providers = EnrichmentProvider.objects.filter(enabled=True)
    for provider in providers:
        impl_cls = REGISTRY.get(provider.kind)
        if impl_cls is None:
            logger.warning("unknown enrichment provider kind=%s", provider.kind)
            continue
        try:
            impl = impl_cls(provider.config)
        except Exception as exc:
            logger.warning("provider %s init failed: %s", provider.name, exc)
            continue
        for value in values:
            if not refresh:
                existing = Enrichment.objects.filter(ioc_value=value, provider=provider.name).first()
                if existing:
                    rows.append(existing)
                    continue
            try:
                hit = impl.lookup(value)
            except ProviderLookupError as exc:
                logger.warning("provider %s lookup failed value=%s: %s", provider.name, value[:80], exc)
                continue
            except Exception as exc:  # provider bug / network error must not break the request
                logger.warning("provider %s error value=%s: %s", provider.name, value[:80], exc)
                continue
            if not hit:
                continue
            row, _ = Enrichment.objects.update_or_create(
                ioc_value=value,
                provider=provider.name,
                defaults={
                    "ioc_type": classify(value),
                    "verdict": hit.get("verdict", "unknown"),
                    "data": hit.get("data") or {},
                },
            )
            rows.append(row)
    return rows


def case_iocs(case) -> list[dict]:
    """Distinct IOCs from the case's linked alerts (dedupe by value)."""
    seen: dict[str, dict] = {}
    for alert in case.alerts.all():
        for ioc in alert.iocs or []:
            value = str(ioc.get("value", "")).strip()
            if value and value not in seen:
                seen[value] = {"value": value, "type": ioc.get("type") or classify(value)}
    return list(seen.values())


def enrich_case(case) -> dict:
    ensure_default_provider()
    iocs = case_iocs(case)
    rows = enrich_values([i["value"] for i in iocs])
    return {
        "iocs": iocs,
        "results": [
            {
                "ioc_value": r.ioc_value,
                "ioc_type": r.ioc_type,
                "provider": r.provider,
                "verdict": r.verdict,
                "data": r.data,
            }
            for r in rows
        ],
    }
