"""Makes the logged-in user's chat mode the default for LLM calls on this request thread.

local_engine injects a mode system prompt on every call; the mode comes from (in order):
explicit call argument > this thread-local value > "work".
Background threads (playbook/agent runs) receive the requesting user's mode explicitly.
"""

from __future__ import annotations

from llm import chat_modes, local_engine


class ChatModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        mode = chat_modes.DEFAULT_MODE
        if user is not None and user.is_authenticated:
            mode = chat_modes.normalize_mode(getattr(user, "chat_mode", None))
        local_engine.set_thread_mode(mode)
        return self.get_response(request)
