"""OpenAI-compatible test double for IntrovertSOC.

Used by automated tests and for UI development when no llamafile is running.
Stdlib only - no third-party dependencies.

Modes (set module attribute ``MODE`` or env FAKE_LLM_MODE before start):
  normal        - sensible canned responses; JSON requests get valid JSON
  flaky         - first chat call returns HTTP 500 (exercises retry), then normal
  garbage       - JSON requests always return prose (exercises failure path)
  garbage_first - first JSON request is prose, second is valid (exercises repair)
  slow          - sleeps 3s before responding (exercises timeouts)

Run: python scripts/fake_llm_server.py [port]   (default 8099)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODE = os.environ.get("FAKE_LLM_MODE", "normal")


def _default_port() -> int:
    if __name__ == "__main__" and len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            pass
    return int(os.environ.get("FAKE_LLM_PORT", "8099"))


PORT = _default_port()

_lock = threading.Lock()
calls = {"chat": 0, "embeddings": 0, "json": 0}
last_payload: dict | None = None

VALID_REPORT = {
    "summary": "Brute-force login attempts against WRK-042 followed by a successful login from a new country.",
    "severity": "high",
    "confidence": "medium",
    "verdict": "likely_compromise",
    "rationale": "37 failed logins then success from an unseen ASN within 2 minutes.",
    "next_steps": ["Isolate WRK-042", "Force password reset", "Review VPN logs"],
}


def reset_state(mode: str | None = None):
    global MODE, last_payload
    with _lock:
        for key in calls:
            calls[key] = 0
        last_payload = None
        if mode is not None:
            MODE = mode


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            self._send(200, {"object": "list", "data": [{"id": "fake-model-q4", "object": "model"}]})
        elif self.path in ("/", "/healthz"):
            self._send(200, {"status": "ok", "mode": MODE})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        global last_payload
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            request = json.loads(raw or b"{}")
        except ValueError:
            request = {}

        if self.path.startswith("/v1/embeddings"):
            with _lock:
                calls["embeddings"] += 1
            inputs = request.get("input") or []
            if isinstance(inputs, str):
                inputs = [inputs]
            data = [
                {"object": "embedding", "index": i, "embedding": [float(i % 7), 1.0, 0.5]}
                for i, _ in enumerate(inputs)
            ]
            self._send(200, {"object": "list", "data": data})
            return

        if not self.path.startswith("/v1/chat/completions"):
            self._send(404, {"error": "not found"})
            return

        with _lock:
            calls["chat"] += 1
            call_no = calls["chat"]
            last_payload = request

        if MODE == "slow":
            time.sleep(3)
        if MODE == "flaky" and call_no == 1:
            self._send(500, {"error": {"message": "transient failure"}})
            return

        messages = request.get("messages") or []
        system_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "system")
        wants_json = "JSON Schema" in system_text

        if wants_json:
            with _lock:
                calls["json"] += 1
                json_no = calls["json"]
            if MODE == "garbage" or (MODE == "garbage_first" and json_no == 1):
                content = "I think the situation is suspicious, but let me explain my reasoning at length."
            else:
                content = "```json\n" + json.dumps(VALID_REPORT) + "\n```"
        elif "SUPER INTROVERT" in system_text:
            content = "STATUS: suspicious\nSEVERITY: high\nACTION: isolate WRK-042"
        elif "INTROVERT MODE" in system_text:
            content = "- Verdict: likely compromise\n- Evidence: 37 failed logins then success\n- Action: isolate host"
        else:
            content = (
                "Assessment: likely compromise of WRK-042.\n\n"
                "Reasoning: authentication anomaly followed by success from a new ASN.\n\n"
                "Next steps:\n1. Isolate host\n2. Reset credentials"
            )

        self._send(
            200,
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "model": request.get("model", "fake-model-q4"),
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            },
        )


def start(port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    """Start the fake server in a daemon thread. Returns (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"fake_llm_server listening on http://127.0.0.1:{PORT} mode={MODE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
