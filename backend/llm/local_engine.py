"""THE single point of LLM integration for IntrovertSOC.

Everything that needs a model - agent nodes, chat, playbooks, knowledge extraction -
imports from this module. Nothing else in the codebase may open a connection to an LLM.

Design rules (see ARCHITECTURE.md §4):
  * plain httpx against the local llamafile OpenAI-compatible endpoint; no cloud SDK,
    no provider list, no API-key surface (an internal placeholder is sent only because
    some servers reject requests without an Authorization header)
  * the selected chat mode's system prompt is injected on EVERY call
  * generous timeouts + 3 retries with backoff (local inference can be slow)
  * structured output via prompt-enforced JSON -> pydantic validation -> one repair
    retry -> LLMOutputError (callers degrade deterministically instead of crashing)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Sequence, TypeVar

import httpx
from pydantic import BaseModel

from . import adapter, chat_modes
from .config import EndpointConfig, get_endpoint_config
from .health import health_check
from .schemas import LLMError, LLMOutputError, LLMUnavailable, validate_json

logger = logging.getLogger("llm.local")

T = TypeVar("T", bound=BaseModel)

RETRY_DELAYS_SECONDS = (0.5, 1.5, 3.5)
RETRYABLE_STATUS = {500, 502, 503, 504, 529}

# Optional caller-side chat-mode override (background threads / playbook runs set this;
# HTTP requests set it automatically via middleware from the logged-in user's preference).
_thread_state = threading.local()


def set_thread_mode(mode: str | None) -> None:
    _thread_state.mode = chat_modes.normalize_mode(mode)


def get_thread_mode() -> str:
    return chat_modes.normalize_mode(getattr(_thread_state, "mode", None))


def user(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


def assistant(text: str) -> dict[str, str]:
    return {"role": "assistant", "content": text}


def _merge_system(mode: str, caller_system: str | None) -> str:
    """Mode prompt on every call; caller's task instructions appended (never replaced)."""
    parts = [chat_modes.get_system_prompt(mode)]
    if caller_system and caller_system.strip():
        parts.append(caller_system.strip())
    return "\n\n".join(parts)


def _prepare_messages(
    messages: Sequence[dict[str, str]],
    *,
    mode: str | None,
    system: str | None,
) -> list[dict[str, str]]:
    resolved_mode = chat_modes.normalize_mode(mode if mode is not None else get_thread_mode())
    merged = _merge_system(resolved_mode, system)
    prepared: list[dict[str, str]] = []
    caller_systems: list[str] = []
    for message in messages:
        if message.get("role") == "system":
            caller_systems.append(str(message.get("content", "")))
        else:
            prepared.append({"role": message["role"], "content": str(message.get("content", ""))})
    if caller_systems:
        merged = merged + "\n\n" + "\n\n".join(s for s in caller_systems if s.strip())
    return [{"role": "system", "content": merged}, *prepared]


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some servers return [{type: text, text: ...}]
        chunks = []
        for part in content:
            if isinstance(part, dict):
                chunks.append(str(part.get("text") or part.get("content") or ""))
            else:
                chunks.append(str(part))
        return "".join(chunks)
    return str(content or "")


class LocalEngine:
    """Stateless client; construct with an explicit config mainly for tests."""

    def __init__(self, config: EndpointConfig | None = None):
        self._config = config

    @property
    def config(self) -> EndpointConfig:
        return self._config or get_endpoint_config()

    # ------------------------------------------------------------------ low-level call
    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        mode: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        timeout: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """One chat completion against the local server. Raises LLMUnavailable/LLMError."""
        cfg = self.config
        payload_messages = _prepare_messages(messages, mode=mode, system=system)
        payload: dict[str, Any] = {
            "model": cfg.model,
            "messages": payload_messages,
            "temperature": temperature,
            "stream": False,
        }
        # Model-family adapter (Phase 10): Qwen3/MiMo templates "think" by default and
        # can leave content empty - disable per-request. Other families get no extra kwarg.
        payload.update(adapter.request_shaping(adapter.resolve_family()))
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resolved_mode = chat_modes.normalize_mode(
            mode if mode is not None else getattr(_thread_state, "mode", None)
        )
        started = time.monotonic()
        last_error: Exception | None = None

        for attempt, delay in enumerate((*RETRY_DELAYS_SECONDS, None)):
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(
                        connect=cfg.connect_timeout,
                        read=timeout or cfg.timeout,
                        write=30.0,
                        pool=cfg.connect_timeout,
                    ),
                    trust_env=False,  # ignore HTTP(S)_PROXY env - no egress outside allowlist
                ) as client:
                    response = client.post(
                        cfg.chat_url,
                        json=payload,
                        headers={"Authorization": f"Bearer {cfg.api_key}"},
                    )
                if response.status_code >= 400:
                    body = response.text[:300]
                    if response.status_code in RETRYABLE_STATUS and delay is not None:
                        last_error = LLMUnavailable(f"HTTP {response.status_code}: {body}")
                        logger.warning(
                            "llm retry attempt=%d status=%d target=%s", attempt + 1, response.status_code, cfg.base_url
                        )
                        time.sleep(delay)
                        continue
                    raise LLMUnavailable(
                        f"Local LLM server at {cfg.base_url} returned HTTP {response.status_code}: {body}"
                    )

                data = json.loads(response.text)
                choices = data.get("choices") or []
                if not choices:
                    raise LLMOutputError(f"Model returned no choices (body: {response.text[:200]!r})")
                message = choices[0].get("message") or {}
                text = adapter.strip_thinking_tags(_content_to_text(message.get("content")))
                if not text.strip() and message.get("reasoning_content"):
                    # Server ignored enable_thinking; never hand back an empty answer.
                    logger.warning("llm empty content with reasoning present - using reasoning as output")
                    text = _content_to_text(message.get("reasoning_content"))
                elapsed_ms = int((time.monotonic() - started) * 1000)
                logger.info(
                    "llm.complete ok target=%s model=%s mode=%s ms=%d chars=%d",
                    cfg.base_url, cfg.model, resolved_mode, elapsed_ms, len(text),
                )
                return text
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if delay is None:
                    break
                logger.warning(
                    "llm retry attempt=%d error=%s target=%s", attempt + 1, type(exc).__name__, cfg.base_url
                )
                time.sleep(delay)
            except json.JSONDecodeError as exc:
                raise LLMOutputError(f"Server returned non-JSON body: {exc}") from exc

        raise LLMUnavailable(
            f"Local LLM server unreachable at {cfg.base_url} after {len(RETRY_DELAYS_SECONDS) + 1} attempts: "
            f"{type(last_error).__name__}: {last_error}"
        )

    # ------------------------------------------------------------------ structured output
    def complete_json(
        self,
        messages: Sequence[dict[str, str]],
        *,
        schema: type[T],
        mode: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        timeout: float | None = None,
        max_tokens: int | None = None,
        max_repair: int = 1,
    ) -> T:
        """Chat completion validated against a pydantic schema.

        Local models are unreliable at native tool/function calling, so we ask for JSON
        in the prompt, validate strictly, and feed validation errors back once (repair).
        A second failure raises LLMOutputError - callers must degrade deterministically.
        """
        json_instructions = (
            (system.strip() + "\n\n" if system else "")
            + "Respond with ONLY one valid JSON object matching this JSON Schema. "
            "No prose, no markdown, no code fences.\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False)
        )
        conversation = list(messages)
        output = self.complete(
            conversation, mode=mode, system=json_instructions, temperature=temperature,
            timeout=timeout, max_tokens=max_tokens,
        )
        try:
            return validate_json(output, schema)
        except LLMOutputError as first_error:
            if max_repair < 1:
                raise
            logger.warning("llm json repair needed: %s", str(first_error)[:200])
            repair = [
                *conversation,
                assistant(output),
                user(
                    "Your previous response was rejected:\n"
                    f"{first_error}\n"
                    "Respond again with ONLY the corrected JSON object, nothing else."
                ),
            ]
            output = self.complete(
                repair, mode=mode, system=json_instructions, temperature=temperature,
                timeout=timeout, max_tokens=max_tokens,
            )
            return validate_json(output, schema)

    # ------------------------------------------------------------------ embeddings (KB)
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embedding vectors from the same local server (llamafile /v1/embeddings).

        Raises LLMUnavailable - knowledge retrieval falls back to keyword search.
        """
        cfg = self.config
        try:
            with httpx.Client(timeout=httpx.Timeout(cfg.connect_timeout, read=cfg.timeout), trust_env=False) as client:
                response = client.post(
                    cfg.embeddings_url,
                    json={"model": cfg.model, "input": list(texts)},
                    headers={"Authorization": f"Bearer {cfg.api_key}"},
                )
                response.raise_for_status()
                data = json.loads(response.text).get("data") or []
                vectors = [item.get("embedding") for item in data]
                if any(v is None for v in vectors) or len(vectors) != len(texts):
                    raise LLMOutputError("Embeddings response did not match input size")
                return [list(map(float, v)) for v in vectors]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LLMUnavailable(f"Local embedding call failed at {cfg.base_url}: {exc}") from exc


engine = LocalEngine()


def complete(messages: Sequence[dict[str, str]], **kwargs: Any) -> str:
    return engine.complete(messages, **kwargs)


def complete_json(messages: Sequence[dict[str, str]], *, schema: type[T], **kwargs: Any) -> T:
    return engine.complete_json(messages, schema=schema, **kwargs)


def embed(texts: Sequence[str]) -> list[list[float]]:
    return engine.embed(texts)


def test_connection() -> dict:
    """Model Settings page 'Test connection' button."""
    status = health_check(force=True)
    cfg = get_endpoint_config()
    return {
        "connected": status.ok,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "server_model": status.server_model,
        "detail": status.detail,
        "latency_ms": status.latency_ms,
    }


__all__ = [
    "LocalEngine",
    "engine",
    "complete",
    "complete_json",
    "embed",
    "user",
    "assistant",
    "test_connection",
    "set_thread_mode",
    "get_thread_mode",
    "LLMError",
    "LLMUnavailable",
    "LLMOutputError",
    "health_check",
]
