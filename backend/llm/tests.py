"""Tests for the single LLM integration point (run against the in-process fake server)."""

import os
import unittest.mock
from unittest import mock

from django.test import SimpleTestCase

from scripts import fake_llm_server

from . import adapter, chat_modes, health, local_engine, schemas
from .config import EndpointConfig
from .schemas import LLMOutputError, LLMUnavailable


class ChatModeTests(SimpleTestCase):
    def test_registry_has_five_modes(self):
        self.assertEqual(
            set(chat_modes.MODE_REGISTRY),
            {"work", "introvert", "super_introvert", "paranoid", "zen"},
        )

    def test_default_is_work(self):
        self.assertEqual(chat_modes.DEFAULT_MODE, "work")
        self.assertEqual(chat_modes.normalize_mode(None), "work")
        self.assertEqual(chat_modes.normalize_mode("bogus"), "work")
        self.assertEqual(chat_modes.normalize_mode("zen"), "zen")

    def test_each_mode_has_distinct_prompt(self):
        prompts = [chat_modes.get_system_prompt(m) for m in chat_modes.MODE_REGISTRY]
        self.assertEqual(len(set(prompts)), 5)
        self.assertIn("SUPER INTROVERT MODE", chat_modes.get_system_prompt("super_introvert"))
        self.assertIn("INTROVERT MODE", chat_modes.get_system_prompt("introvert"))
        self.assertIn("PARANOID MODE", chat_modes.get_system_prompt("paranoid"))
        self.assertIn("ZEN MODE", chat_modes.get_system_prompt("zen"))

    def test_mode_token_budgets(self):
        self.assertEqual(
            set(chat_modes.MODE_MAX_TOKENS),
            {"work", "introvert", "super_introvert", "paranoid", "zen"},
        )
        self.assertEqual(chat_modes.budget("paranoid"), 4096)
        self.assertEqual(chat_modes.budget("zen"), 768)
        self.assertEqual(chat_modes.budget(None), 2048)
        self.assertGreater(chat_modes.budget("paranoid"), chat_modes.budget("super_introvert"))


class AdapterUnitTests(SimpleTestCase):
    def test_detect_family(self):
        self.assertEqual(adapter.detect_family("MiMo-V2.6-Flash-RL"), "mimo")
        self.assertEqual(adapter.detect_family("qwen3-4b-instruct-q4_k_m.gguf"), "qwen3")
        self.assertEqual(adapter.detect_family("TheBloke/Qwen2.5-7B"), "qwen")
        self.assertEqual(adapter.detect_family("mistralai/Ministral-8B"), "mistral")
        self.assertEqual(adapter.detect_family("some-random-model"), "unknown")
        self.assertEqual(adapter.detect_family(None), "unknown")

    def test_request_shaping_by_family(self):
        shaped = {"chat_template_kwargs": {"enable_thinking": False}}
        self.assertEqual(adapter.request_shaping("qwen3"), shaped)
        self.assertEqual(adapter.request_shaping("mimo"), shaped)
        self.assertEqual(adapter.request_shaping("unknown"), shaped)
        self.assertEqual(adapter.request_shaping("mistral"), {})
        self.assertEqual(adapter.request_shaping("llama"), {})

    def test_strip_thinking_tags(self):
        self.assertEqual(adapter.strip_thinking_tags("plain answer"), "plain answer")
        self.assertEqual(
            adapter.strip_thinking_tags("```thinking\ndangerous step\n```\nreal answer"),
            "real answer",
        )
        self.assertEqual(adapter.strip_thinking_tags("no fence\n```thinking\npartial"), "no fence")
        self.assertEqual(adapter.strip_thinking_tags(""), "")
        self.assertIsNone(adapter.strip_thinking_tags(None))

    def test_context_info_defaults(self):
        with mock.patch("llm.adapter._db_override", return_value=None), mock.patch(
            "llm.adapter.health_check"
        ) as hc:
            hc.return_value = mock.Mock(context_length=None)
            self.assertEqual(adapter.context_info(), (adapter.DEFAULT_CONTEXT_WINDOW, "default"))
            hc.return_value = mock.Mock(context_length=262_144)
            self.assertEqual(adapter.context_info(), (262_144, "server"))
            hc.return_value = mock.Mock(context_length=mock.Mock())  # never JSON-safe
            self.assertEqual(adapter.context_info(), (adapter.DEFAULT_CONTEXT_WINDOW, "default"))
            hc.return_value = mock.Mock(context_length="131072")
            self.assertEqual(adapter.context_info(), (131_072, "server"))

    def test_context_info_override_and_clamps(self):
        with mock.patch("llm.adapter._db_override", return_value=999_999_999):
            self.assertEqual(adapter.context_info(), (adapter.MAX_CONTEXT_WINDOW, "override"))

    def test_wants_inline_kb_threshold(self):
        with mock.patch("llm.adapter.context_window", return_value=131_072):
            self.assertTrue(adapter.wants_inline_kb())
        with mock.patch("llm.adapter.context_window", return_value=131_071):
            self.assertFalse(adapter.wants_inline_kb())
        with mock.patch("llm.adapter.context_window", return_value=1_048_576):
            self.assertTrue(adapter.wants_inline_kb())


class JsonExtractionTests(SimpleTestCase):
    def test_plain_json(self):
        self.assertEqual(schemas.extract_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(schemas.extract_json('Here you go:\n```json\n{"a": 1}\n```\nDone'), {"a": 1})

    def test_prose_wrapped_json(self):
        self.assertEqual(schemas.extract_json('Sure! {"verdict": "benign"} hope that helps'), {"verdict": "benign"})

    def test_no_json_returns_none(self):
        self.assertIsNone(schemas.extract_json("no json here"))


class LocalEngineTests(SimpleTestCase):
    server = None
    base_url = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server, cls.base_url = fake_llm_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        super().tearDownClass()

    def setUp(self):
        fake_llm_server.reset_state(mode="normal")
        health.invalidate_cache()
        self.engine = local_engine.LocalEngine(
            EndpointConfig(
                base_url=self.base_url,
                model="fake-model-q4",
                gguf_path="",
                connect_timeout=2.0,
                timeout=10.0,
                api_key="local",
                source="env",
            )
        )
        self._orig_delays = local_engine.RETRY_DELAYS_SECONDS
        local_engine.RETRY_DELAYS_SECONDS = (0.01, 0.01)

    def tearDown(self):
        local_engine.RETRY_DELAYS_SECONDS = self._orig_delays
        local_engine.set_thread_mode(None)

    def test_complete_returns_text(self):
        out = self.engine.complete([local_engine.user("hello")])
        self.assertIn("likely compromise", out)

    def test_mode_system_prompt_is_injected_on_every_call(self):
        self.engine.complete([local_engine.user("hi")], mode="super_introvert")
        sent = fake_llm_server.last_payload["messages"]
        self.assertEqual(sent[0]["role"], "system")
        self.assertIn("SUPER INTROVERT MODE", sent[0]["content"])

    def test_caller_system_is_merged_not_replaced(self):
        self.engine.complete(
            [local_engine.user("hi")], mode="introvert", system="You are a parser. Output facts only."
        )
        system = fake_llm_server.last_payload["messages"][0]["content"]
        self.assertIn("INTROVERT MODE", system)
        self.assertIn("You are a parser.", system)

    def test_thread_mode_used_when_no_explicit_mode(self):
        local_engine.set_thread_mode("introvert")
        self.engine.complete([local_engine.user("hi")])
        self.assertIn("INTROVERT MODE", fake_llm_server.last_payload["messages"][0]["content"])

    def test_retry_on_500_then_success(self):
        fake_llm_server.reset_state(mode="flaky")
        out = self.engine.complete([local_engine.user("hello")])
        self.assertIn("likely compromise", out)
        self.assertEqual(fake_llm_server.calls["chat"], 2)

    def test_complete_json_valid(self):
        from .schemas import LLMOutputError  # noqa: F401

        import pydantic

        class Report(pydantic.BaseModel):
            summary: str
            severity: str
            confidence: str
            verdict: str
            rationale: str
            next_steps: list[str]

        report = self.engine.complete_json([local_engine.user("assess")], schema=Report)
        self.assertEqual(report.severity, "high")
        self.assertEqual(report.verdict, "likely_compromise")

    def test_complete_json_repairs_bad_first_output(self):
        import pydantic

        class Report(pydantic.BaseModel):
            summary: str
            severity: str
            confidence: str
            verdict: str
            rationale: str
            next_steps: list[str]

        fake_llm_server.reset_state(mode="garbage_first")
        report = self.engine.complete_json([local_engine.user("assess")], schema=Report)
        self.assertEqual(report.verdict, "likely_compromise")
        self.assertEqual(fake_llm_server.calls["chat"], 2)

    def test_complete_json_raises_after_failed_repair(self):
        import pydantic

        class Report(pydantic.BaseModel):
            summary: str

        fake_llm_server.reset_state(mode="garbage")
        with self.assertRaises(LLMOutputError):
            self.engine.complete_json([local_engine.user("assess")], schema=Report)

    def test_unreachable_server_raises_llm_unavailable(self):
        dead = local_engine.LocalEngine(
            EndpointConfig(
                base_url="http://127.0.0.1:9",  # discard port, connection refused
                model="x",
                gguf_path="",
                connect_timeout=1.0,
                timeout=1.0,
                api_key="local",
                source="env",
            )
        )
        with self.assertRaises(LLMUnavailable) as ctx:
            dead.complete([local_engine.user("hi")])
        self.assertIn("http://127.0.0.1:9", str(ctx.exception))

    def test_embed_returns_vectors(self):
        vectors = self.engine.embed(["a", "b"])
        self.assertEqual(len(vectors), 2)

    def test_health_check_up_and_down(self):
        with unittest.mock.patch.dict(
            os.environ, {"LLAMAFILE_BASE_URL": self.base_url}
        ):
            status = health.health_check(force=True)
            self.assertTrue(status.ok)
            self.assertEqual(status.server_model, "fake-model-q4")

        with unittest.mock.patch.dict(
            os.environ, {"LLAMAFILE_BASE_URL": "http://127.0.0.1:9"}
        ):
            health.invalidate_cache()
            status = health.health_check(force=True)
            self.assertFalse(status.ok)
            self.assertIn("Local model server not detected", health.unavailable_banner(status))
