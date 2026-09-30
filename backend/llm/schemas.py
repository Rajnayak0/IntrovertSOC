"""Errors and JSON-recovery helpers for local-model outputs.

Local GGUF models often wrap JSON in prose or ```json fences, and occasionally emit
truncated/invalid JSON. ``complete_json`` in local_engine uses these helpers for a
validate -> repair -> deterministic-fallback cycle instead of native tool-calling.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


class LLMError(Exception):
    """Base class for local LLM failures."""


class LLMUnavailable(LLMError):
    """The local llamafile server could not be reached / errored after retries."""


class LLMOutputError(LLMError):
    """The model responded but the output could not be parsed/validated, even after repair."""


def extract_json(text: str) -> Any | None:
    """Best-effort extraction of the first JSON object/array from model output.

    Handles: code fences, leading prose ("Here is the JSON:"), trailing commentary.
    Returns Python data or None if nothing parseable is found.
    """
    if not text:
        return None

    candidates: list[str] = []
    for match in _FENCE_RE.finditer(text):
        candidates.append(match.group(1).strip())

    stripped = text.strip()
    candidates.append(stripped)

    # First balanced {...} or [...] span in the raw text.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end > start:
            candidates.append(stripped[start : end + 1])

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def validate_json(text: str, schema: type[T]) -> T:
    """Parse model output into ``schema`` or raise LLMOutputError with a usable detail."""
    data = extract_json(text)
    if data is None:
        snippet = (text or "").strip()[:400]
        raise LLMOutputError(f"No JSON found in model output. Output started with: {snippet!r}")
    try:
        if not isinstance(data, dict):
            raise LLMOutputError(f"Expected a JSON object, got {type(data).__name__}")
        return schema.model_validate(data)
    except ValidationError as exc:
        raise LLMOutputError(f"JSON did not match schema: {exc.errors()[:5]}") from exc
