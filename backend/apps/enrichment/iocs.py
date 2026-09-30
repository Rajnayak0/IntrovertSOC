"""Deterministic IOC extraction - regex first, never replaced by the model
(ARCHITECTURE.md §5). Runs on every Alert save (no LLM, no network)."""

from __future__ import annotations

import ipaddress
import re

URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,24}\b", re.IGNORECASE)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b(?:[a-f0-9]{1,4}:){2,7}[a-f0-9]{1,4}\b", re.IGNORECASE)
DOMAIN_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})\b", re.IGNORECASE)
MD5_RE = re.compile(r"\b[a-f0-9]{32}\b", re.IGNORECASE)
SHA1_RE = re.compile(r"\b[a-f0-9]{40}\b", re.IGNORECASE)
SHA256_RE = re.compile(r"\b[a-f0-9]{64}\b", re.IGNORECASE)

_DOMAIN_TLDS_SKIP = {"log", "txt", "json", "yml", "yaml", "py", "sh", "exe", "dll", "js", "css"}


def classify(value: str) -> str:
    """IOC type for a single value (used by enrichment rows)."""
    if URL_RE.fullmatch(value):
        return "url"
    try:
        ipaddress.ip_address(value)
        return "ip"
    except ValueError:
        pass
    if re.fullmatch(r"[a-f0-9]{32}", value, re.IGNORECASE):
        return "md5"
    if re.fullmatch(r"[a-f0-9]{40}", value, re.IGNORECASE):
        return "sha1"
    if re.fullmatch(r"[a-f0-9]{64}", value, re.IGNORECASE):
        return "sha256"
    if EMAIL_RE.fullmatch(value):
        return "email"
    if DOMAIN_RE.fullmatch(value):
        return "domain"
    return "other"


def extract_iocs(*texts: str) -> list[dict]:
    """Regex extraction with dedupe; priority url > ip > hash > email > domain."""
    blob = "\n".join(t for t in texts if t)
    found: list[str] = []

    def add(value: str) -> None:
        value = value.rstrip(".,;:)]}>'\"")
        if value and value.lower() not in {f.lower() for f in found}:
            found.append(value)

    for match in URL_RE.findall(blob):
        add(match)
    for match in (*IPV4_RE.findall(blob), *IPV6_RE.findall(blob)):
        try:
            ipaddress.ip_address(match)
            add(match)
        except ValueError:
            continue
    for match in (*SHA256_RE.findall(blob), *SHA1_RE.findall(blob), *MD5_RE.findall(blob)):
        add(match)
    for match in EMAIL_RE.findall(blob):
        add(match)
    for match in DOMAIN_RE.findall(blob):
        if match.lower().rsplit(".", 1)[-1] in _DOMAIN_TLDS_SKIP:
            continue
        if any(match in f for f in found):  # substring of a URL already captured
            continue
        add(match)

    return [{"type": classify(v), "value": v} for v in found]


def extract_from_alert(alert) -> list[dict]:
    import json

    raw = json.dumps(getattr(alert, "raw_data", {}) or {}, default=str)
    return extract_iocs(alert.title, alert.desc, raw)
