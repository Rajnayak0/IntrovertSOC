"""Pluggable enrichment providers (ARCHITECTURE.md §4 "pluggable edges").

- local_feed: CSV file shipped with the repo (default, fully offline)
- http_lookup: user-owned endpoint (MISP/OpenCTI-style), opt-in only; never a baked-in
  cloud URL (MIGRATION #14-16). Uses httpx with trust_env=False (no proxy egress).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from urllib.parse import quote

import httpx

logger = logging.getLogger("apps.enrichment")


class ProviderLookupError(Exception):
    pass


def _normalize_verdict(value: str | None) -> str:
    text = (value or "").strip().lower()
    for verdict in ("malicious", "suspicious", "clean", "unknown"):
        if verdict in text:
            return verdict
    if text in {"bad", "blocklist", "blacklist", "mal", "apt"}:
        return "malicious"
    if text in {"ok", "good", "allowlist", "whitelist", "benign"}:
        return "clean"
    return "unknown"


class LocalFeedProvider:
    """CSV with columns value,type,verdict,note - re-read when the file changes."""

    def __init__(self, config: dict):
        self.path = Path(str(config.get("path", "")))
        self._mtime: float | None = None
        self._rows: dict[str, dict] = {}

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            raise ProviderLookupError(f"feed file not found: {self.path}")
        mtime = self.path.stat().st_mtime
        if self._mtime == mtime:
            return self._rows
        rows: dict[str, dict] = {}
        with self.path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                value = (row.get("value") or "").strip().lower()
                if value:
                    rows[value] = {
                        "verdict": _normalize_verdict(row.get("verdict")),
                        "type": (row.get("type") or "").strip(),
                        "note": (row.get("note") or "").strip(),
                    }
        self._mtime = mtime
        self._rows = rows
        return rows

    def lookup(self, value: str) -> dict | None:
        hit = self._load().get(value.strip().lower())
        if not hit:
            return None
        return {"verdict": hit["verdict"], "data": {"note": hit["note"], "type": hit["type"]}}


class HttpLookupProvider:
    """GET a user-configured URL template: {value} placeholder, JSON response.

    config: {url_template, verdict_path (dot path, optional), verdict_map (obj, optional)}
    """

    def __init__(self, config: dict):
        self.template = str(config.get("url_template", ""))
        self.verdict_path = str(config.get("verdict_path", "") or "")
        self.verdict_map = dict(config.get("verdict_map") or {})
        self.timeout = float(config.get("timeout", 5))

    def lookup(self, value: str) -> dict | None:
        if "{value}" not in self.template:
            raise ProviderLookupError("url_template must contain {value}")
        url = self.template.replace("{value}", quote(value, safe=""))
        if not url.startswith(("http://", "https://")):
            raise ProviderLookupError("url_template must be http(s)")
        logger.info("enrichment http target=%s value=%s", url, value)
        with httpx.Client(timeout=httpx.Timeout(self.timeout), trust_env=False) as client:
            response = client.get(url)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise ProviderLookupError(f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderLookupError(f"non-JSON response: {exc}") from exc

        verdict_raw = ""
        if self.verdict_path:
            cursor = payload
            for part in self.verdict_path.split("."):
                cursor = cursor.get(part) if isinstance(cursor, dict) else None
                if cursor is None:
                    break
            verdict_raw = str(cursor or "")
        if self.verdict_map:
            verdict = _normalize_verdict(self.verdict_map.get(verdict_raw.lower(), verdict_raw))
        else:
            verdict = _normalize_verdict(verdict_raw)
        if verdict == "unknown" and verdict_raw == "" and payload:
            verdict = "suspicious"  # endpoint responded with data but no explicit verdict
        return {"verdict": verdict, "data": {"raw": payload if isinstance(payload, dict) else {"result": payload}}}


REGISTRY = {
    "local_feed": LocalFeedProvider,
    "http_lookup": HttpLookupProvider,
}
