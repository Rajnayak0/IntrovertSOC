"""Health check for the local llamafile server.

Cached for a few seconds so the UI can poll freely. Never raises - a down server is a
normal state for this app (the banner tells the user how to start it), not a crash.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass

import httpx

from .config import get_endpoint_config

CACHE_TTL_SECONDS = 15.0
REQUEST_TIMEOUT_SECONDS = 3.0


@dataclass
class HealthStatus:
    ok: bool
    base_url: str
    detail: str
    server_model: str | None = None
    context_length: int | None = None
    latency_ms: int | None = None
    checked_at: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def _parse_context_length(payload: dict, model: dict | None) -> int | None:
    """Some OpenAI-compatible servers report context size in /v1/models; most don't."""
    for source in (model or {}, payload):
        for key in ("context_length", "context_window", "max_context_length", "n_ctx"):
            value = source.get(key) if isinstance(source, dict) else None
            try:
                if value:
                    return int(value)
            except (TypeError, ValueError):
                continue
    return None


_lock = threading.Lock()
_cache: HealthStatus | None = None


def unavailable_banner(status: HealthStatus) -> str:
    """The exact in-app message required when no local model server is detected."""
    return (
        f"Local model server not detected — start your llamafile at {status.base_url} "
        "to enable AI features."
    )


def _probe() -> HealthStatus:
    cfg = get_endpoint_config()
    started = time.monotonic()
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as client:
            response = client.get(cfg.models_url, headers=_headers(cfg.api_key))
            if response.status_code >= 400:
                # Some OpenAI-compatible servers don't expose /v1/models; a live root is enough.
                root = client.get(f"{cfg.base_url}/", headers=_headers(cfg.api_key))
                if root.status_code >= 500:
                    return HealthStatus(
                        ok=False,
                        base_url=cfg.base_url,
                        detail=f"Server responded with HTTP {root.status_code}",
                        latency_ms=int((time.monotonic() - started) * 1000),
                    )
                return HealthStatus(
                    ok=True,
                    base_url=cfg.base_url,
                    detail="Server reachable (no /v1/models endpoint)",
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            server_model = None
            context_length = None
            try:
                payload = json.loads(response.text)
                data = payload.get("data") or []
                model0 = data[0] if data and isinstance(data[0], dict) else None
                if model0:
                    server_model = model0.get("id")
                context_length = _parse_context_length(payload, model0)
            except (ValueError, AttributeError, IndexError):
                pass
            return HealthStatus(
                ok=True,
                base_url=cfg.base_url,
                detail="Connected",
                server_model=server_model,
                context_length=context_length,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
    except httpx.HTTPError as exc:
        return HealthStatus(
            ok=False,
            base_url=cfg.base_url,
            detail=f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def health_check(force: bool = False) -> HealthStatus:
    """Return cached (<=15s) health, probing the local server when stale."""
    global _cache
    with _lock:
        now = time.time()
        if not force and _cache is not None and (now - _cache.checked_at) < CACHE_TTL_SECONDS:
            return _cache
        status = _probe()
        status.checked_at = now
        _cache = status
        return status


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None
