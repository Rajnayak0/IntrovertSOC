"""Model-family adapter: detect what the local server is serving and adapt to it.

Phase 10 (MIGRATION): the old code had a Qwen3-only patch hard-coded in local_engine.
This module generalizes it:

  * family detection from server-reported model id + configured labels/GGUF path
  * per-family request shaping (chat_template_kwargs.enable_thinking for the Qwen3 /
    MiMo template family - both emit ```thinking blocks when thinking is on)
  * thinking-tag cleanup for any model that leaks reasoning into content
  * context-window detection: DB override -> server-reported -> default, which drives
    the adaptive KB strategy (>=128k context: feed the ENTIRE knowledge base inline,
    no retrieval; smaller: keep top-K keyword search)

Nothing here opens connections except through :mod:`llm.health` (cached) - the
NETWORK.md allowlist is unchanged.
"""

from __future__ import annotations

import logging
import re

from .config import get_endpoint_config
from .health import health_check

logger = logging.getLogger("llm.adapter")

DEFAULT_CONTEXT_WINDOW = 32_768
MIN_CONTEXT_FOR_INLINE_KB = 131_072  # 128k tokens: inline the whole KB, skip retrieval
MAX_CONTEXT_WINDOW = 1_048_576

# Families whose Jinja chat template honours chat_template_kwargs.enable_thinking
# (Qwen3 and MiMo-V2.6 both ship the same ```thinking ... ``` protocol).
_THINKING_FAMILIES = {"qwen3", "qwen", "mimo", "unknown"}

_CTX_KEYS = ("context_length", "context_window", "max_context_length", "n_ctx")

# ```thinking ... ``` (possibly unclosed at end of output)
_THINK_BLOCK_RE = re.compile(r"```thinking.*?(?:```|$)", re.DOTALL)
_STRAY_THINK_TAG_RE = re.compile(r"```(?:/)?thinking```?")


def detect_family(name: str | None) -> str:
    """Best-effort model family from an id/path/label. Lowercase substring rules."""
    n = (name or "").lower()
    if "mimo" in n:
        return "mimo"
    if "qwen3" in n:
        return "qwen3"
    if "qwen" in n:
        return "qwen"
    if "gpt-oss" in n or "gpt_oss" in n:
        return "gpt-oss"
    if "mistral" in n or "ministral" in n or "mixtral" in n:
        return "mistral"
    if "gemma" in n:
        return "gemma"
    if "phi" in n:
        return "phi"
    if "llama" in n:
        return "llama"
    return "unknown"


def resolve_family() -> str:
    """Family from every local string we have: server-reported id, GGUF path, label.

    Never raises - detection is best-effort and unknown stays usable.
    """
    try:
        cfg = get_endpoint_config()
        server_model = health_check().server_model
        blob = f"{server_model or ''} {cfg.gguf_path} {cfg.model}"
        family = detect_family(blob)
        if family == "unknown" and server_model:
            logger.debug("model family unknown for server id %s", server_model)
        return family
    except Exception:  # pragma: no cover - defensive: adapter must never break a call
        return "unknown"


def request_shaping(family: str) -> dict:
    """Extra payload fields for this family (merged into the chat completion body)."""
    if family in _THINKING_FAMILIES:
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


def strip_thinking_tags(text: str) -> str:
    """Remove ```thinking blocks a template leaked into content (MiMo/Qwen3-family)."""
    if not text or "```thinking" not in text:
        return text
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _STRAY_THINK_TAG_RE.sub("", cleaned)
    return cleaned.strip()


def _db_override() -> int | None:
    try:
        from apps.modelconfig.models import ModelConfig

        row = ModelConfig.get_solo()
        if row and row.context_window:
            return int(row.context_window)
    except Exception:  # pragma: no cover - DB unavailable (fresh test DB, etc.)
        pass
    return None


def context_info() -> tuple[int, str]:
    """(effective context window, source): override -> server -> default.

    Tolerant of mocked/test health objects: only int/str ``context_length``
    values are honoured (a ``Mock`` attribute would otherwise crash min()/int()).
    """
    override = _db_override()
    if override:
        return min(override, MAX_CONTEXT_WINDOW), "override"
    reported = None
    try:
        raw = health_check().context_length
    except Exception:
        raw = None
    if isinstance(raw, bool):
        raw = None
    elif isinstance(raw, str):
        try:
            raw = int(float(raw.strip()))
        except (TypeError, ValueError):
            raw = None
    if isinstance(raw, int) and raw > 0:
        reported = raw
    if reported:
        return min(reported, MAX_CONTEXT_WINDOW), "server"
    return DEFAULT_CONTEXT_WINDOW, "default"


def context_window() -> int:
    return context_info()[0]


def wants_inline_kb() -> bool:
    """True when the context window is big enough to feed the ENTIRE KB in one call."""
    return context_window() >= MIN_CONTEXT_FOR_INLINE_KB
