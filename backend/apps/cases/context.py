"""Readable case snapshot shared by the investigation graph, ask_agent, and playbooks."""

from __future__ import annotations


def format_case_context(case) -> str:
    lines = [
        f"Case {case.case_id}: {case.title}",
        f"Status: {case.status}; severity: {case.severity or 'unset'}; priority: {case.priority or 'unset'}",
        f"Description: {case.description or '-'}",
        f"Tags: {', '.join(case.tags) if case.tags else '-'}",
        f"Correlation: {case.correlation_uid or '-'}",
        "",
        "Alerts:",
    ]
    alerts = list(case.alerts.all()[:50])
    if not alerts:
        lines.append("- (no linked alerts)")
    ioc_values: list[str] = []
    for a in alerts:
        iocs = ", ".join(str(i.get("value", "")) for i in a.iocs) if a.iocs else "-"
        lines.append(
            f"- {a.alert_id} [{a.severity}/{a.status}] {a.title} (rule: {a.rule_name or a.rule_id or '-'}; iocs: {iocs})"
        )
        for ioc in a.iocs or []:
            if ioc.get("value") and ioc["value"] not in ioc_values:
                ioc_values.append(ioc["value"])
    lines.append("")
    lines.append("Recent events:")
    events = list(case.events.order_by("-created_at")[:8])
    events.reverse()
    if not events:
        lines.append("- (none)")
    for e in events:
        lines.append(f"- {e.created_at:%Y-%m-%d %H:%M} [{e.kind}] {e.message}")

    if ioc_values:
        from apps.enrichment.models import Enrichment  # local import: app-order safe

        hits = Enrichment.objects.filter(ioc_value__in=ioc_values).order_by("-created_at")
        if hits:
            lines.append("")
            lines.append("Enrichment:")
            seen: set[tuple[str, str]] = set()
            for h in hits:
                key = (h.ioc_value, h.provider)
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {h.ioc_value}: {h.verdict} ({h.provider})")
    return "\n".join(lines)
