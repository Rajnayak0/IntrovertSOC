"""Endpoint configuration for the local LLM server.

Resolution order (first non-empty wins):
  1. DB override  - apps.modelconfig.ModelConfig, edited from the Model Settings page
  2. .env         - LLAMAFILE_* variables
  3. defaults     - http://127.0.0.1:8080, model "local-model"

There is no API-key concept. ``api_key`` below is an internal placeholder ("local") that is
sent only because some OpenAI-compatible servers reject requests without an Authorization
header. It is never displayed, never stored per-provider, and never editable in the UI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DUMMY_API_KEY = "local"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, "") or "").strip() or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class EndpointConfig:
    base_url: str
    model: str
    gguf_path: str
    connect_timeout: float
    timeout: float
    api_key: str
    source: str  # "db" | "env" | "default" - shown in logs / Model Settings for clarity

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    @property
    def models_url(self) -> str:
        return f"{self.base_url}/v1/models"

    @property
    def embeddings_url(self) -> str:
        return f"{self.base_url}/v1/embeddings"


def _env_base_url() -> tuple[str, str]:
    explicit = _env("LLAMAFILE_BASE_URL")
    if explicit:
        return explicit.rstrip("/"), "env"
    host = _env("LLAMAFILE_HOST", DEFAULT_HOST) or DEFAULT_HOST
    port = _env_int("LLAMAFILE_PORT", DEFAULT_PORT)
    return f"http://{host}:{port}", "env"


def get_endpoint_config() -> EndpointConfig:
    base_url, source = _env_base_url()
    model = _env("LLAMAFILE_MODEL", "local-model") or "local-model"
    gguf_path = _env("LLAMAFILE_MODEL_PATH")

    # DB override (Model Settings page) - imported lazily to avoid app-loading cycles.
    try:
        from apps.modelconfig.models import ModelConfig

        row = ModelConfig.get_solo()
        if row is not None:
            if (row.base_url or "").strip():
                base_url, source = row.base_url.strip().rstrip("/"), "db"
            if (row.model or "").strip():
                model = row.model.strip()
            if (row.gguf_path or "").strip():
                gguf_path = row.gguf_path.strip()
    except Exception:  # DB not ready yet (migrations, tests) -> env values are fine
        pass

    return EndpointConfig(
        base_url=base_url,
        model=model,
        gguf_path=gguf_path,
        connect_timeout=float(_env_int("LLAMAFILE_CONNECT_TIMEOUT", 5)),
        timeout=float(_env_int("LLAMAFILE_TIMEOUT", 180)),
        api_key=_env("LLAMAFILE_API_KEY", DUMMY_API_KEY) or DUMMY_API_KEY,
        source=source,
    )
