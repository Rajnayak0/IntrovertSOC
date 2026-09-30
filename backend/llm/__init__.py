"""IntrovertSOC LLM package - the only place in the codebase allowed to reach a model."""

from .local_engine import (  # noqa: F401
    LLMError,
    LLMOutputError,
    LLMUnavailable,
    assistant,
    complete,
    complete_json,
    embed,
    engine,
    health_check,
    set_thread_mode,
    test_connection,
    user,
)
