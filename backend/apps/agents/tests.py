"""Investigation graph tests: happy path, degraded fallbacks, model-down UX, roles, modes."""

import json
from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.cases.models import Case, CaseEvent
from llm.schemas import LLMOutputError

from .graphs import Assessment, run_investigation
from .graphs import _assess, _load_context, _report, _summarize


def _health_ok():
    return mock.Mock(ok=True, detail="Connected", server_model="qwen.gguf", latency_ms=12, checked_at=0.0)


def _health_down():
    return mock.Mock(ok=False, detail="refused", server_model=None, latency_ms=2, checked_at=0.0)


class InvestigationNodeTests(APITestCase):
    """Node-level tests without HTTP (deterministic pre/post-processing)."""

    def setUp(self):
        self.case = Case.objects.create(title="Node case", severity="Medium")
        self.state = {"case_pk": self.case.pk, "mode": "work", "degraded": []}

    def test_load_context_includes_alerts_and_events(self):
        from apps.alerts.models import Alert

        Alert.objects.create(title="Beacon detected", severity="High", case=self.case)
        CaseEvent.objects.create(case=self.case, kind="system", message="Case created")
        out = _load_context(self.state)
        self.assertIn("Node case", out["context"])
        self.assertIn("Beacon detected", out["context"])
        self.assertIn("Case created", out["context"])
        self.assertEqual(out["case"]["severity"], "Medium")

    def test_summarize_degrades_to_empty_on_llm_error(self):
        with mock.patch("apps.agents.graphs.local_engine") as eng:
            eng.complete.side_effect = LLMOutputError("nope")
            out = _summarize({**self.state, "context": "ctx"})
        self.assertEqual(out["summary"], "")
        self.assertEqual(out["degraded"], ["summarize"])

    def test_assess_fallback_keeps_case_severity_low_confidence(self):
        with mock.patch("apps.agents.graphs.local_engine") as eng:
            eng.complete_json.side_effect = LLMOutputError("bad json")
            out = _assess({**self.state, "context": "ctx", "case": {"severity": "Medium"}})
        self.assertEqual(out["assessment"]["severity"], "Medium")
        self.assertEqual(out["assessment"]["confidence"], "low")
        self.assertEqual(out["assessment"]["verdict"], "Insufficient Data")
        self.assertIn("assess", out["degraded"])

    def test_report_failure_returns_partial_prefix(self):
        with mock.patch("apps.agents.graphs.local_engine") as eng:
            eng.complete.side_effect = LLMOutputError("boom")
            out = _report({**self.state, "context": "ctx", "assessment": {}})
        self.assertTrue(out["report_md"].startswith("partial"))
        self.assertIn("report", out["degraded"])


class InvestigationApiTests(APITestCase):
    def setUp(self):
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.analyst.chat_mode = "super_introvert"
        self.analyst.save(update_fields=["chat_mode"])
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)
        self.case = Case.objects.create(title="API case", severity="Low", description="desc")

    def _patch_model(self, complete_return="# Report\nAll good", assess=None):
        eng = mock.Mock()
        eng.complete.return_value = complete_return
        eng.complete_json.return_value = assess or Assessment(
            severity="High", confidence="high", verdict="True Positive",
            rationale="beacon + brute force", next_steps=["isolate host", "reset creds"],
        )
        eng.user.side_effect = lambda t: {"role": "user", "content": t}
        eng.get_thread_mode.return_value = "super_introvert"
        return mock.patch("apps.agents.graphs.local_engine", new=eng), eng

    def test_happy_path_writes_ai_fields_report_and_audit(self):
        self.client.login(username="ana", password="analyst-pass-123")
        eng_patch, eng = self._patch_model()
        with eng_patch, mock.patch("apps.agents.views.health_check", return_value=_health_ok()):
            resp = self.client.post(f"/api/cases/{self.case.pk}/investigate/", {}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["degraded"], [])
        self.assertEqual(resp.data["mode"], "super_introvert")

        self.case.refresh_from_db()
        self.assertEqual(self.case.severity_ai, "High")
        self.assertEqual(self.case.confidence_ai, "high")
        self.assertEqual(self.case.verdict_ai, "True Positive")

        report = json.loads(self.case.investigation_report_ai_json)
        self.assertEqual(report["report_md"], "# Report\nAll good")
        self.assertEqual(report["mode"], "super_introvert")
        self.assertEqual(report["assessment"]["next_steps"], ["isolate host", "reset creds"])
        self.assertEqual(report["degraded"], [])

        self.assertTrue(CaseEvent.objects.filter(case=self.case, kind="system", message__contains="AI investigation").exists())
        self.assertTrue(AuditLog.objects.filter(action="update", metadata__mode="super_introvert").exists())

        # mode rules: pipeline nodes fixed work; report node uses caller's mode
        summarize_kwargs = eng.complete.call_args_list[0].kwargs
        report_kwargs = eng.complete.call_args_list[1].kwargs
        self.assertEqual(summarize_kwargs["mode"], "work")
        self.assertEqual(report_kwargs["mode"], "super_introvert")
        self.assertEqual(eng.complete_json.call_args.kwargs["mode"], "work")

        detail = self.client.get(f"/api/cases/{self.case.pk}/").data
        self.assertEqual(detail["severity_ai"], "High")
        self.assertIn("AI investigation", " ".join(e["message"] for e in detail["events"]))

    def test_degraded_assess_marks_report_and_event(self):
        self.client.login(username="ana", password="analyst-pass-123")
        eng_patch, eng = self._patch_model()
        eng.complete_json.side_effect = LLMOutputError("model rambled")
        with eng_patch, mock.patch("apps.agents.views.health_check", return_value=_health_ok()):
            resp = self.client.post(f"/api/cases/{self.case.pk}/investigate/", {}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn("assess", resp.data["degraded"])
        self.case.refresh_from_db()
        self.assertEqual(self.case.severity_ai, "Low")  # falls back to case severity
        self.assertEqual(self.case.confidence_ai, "low")
        report = json.loads(self.case.investigation_report_ai_json)
        self.assertIn("assess", report["degraded"])
        self.assertTrue(
            CaseEvent.objects.filter(case=self.case, message__contains="[degraded: assess]").exists()
        )

    def test_model_down_returns_503_with_banner(self):
        self.client.login(username="ana", password="analyst-pass-123")
        with mock.patch("apps.agents.views.health_check", return_value=_health_down()):
            resp = self.client.post(f"/api/cases/{self.case.pk}/investigate/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("Local model server not detected", resp.data["detail"])

    def test_viewer_cannot_run(self):
        self.client.login(username="vie", password="viewer-pass-123")
        with mock.patch("apps.agents.views.health_check", return_value=_health_ok()):
            resp = self.client.post(f"/api/cases/{self.case.pk}/investigate/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_case_404(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post("/api/cases/9999/investigate/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_run_service_entry_point(self):
        eng_patch, _ = self._patch_model()
        with eng_patch:
            outcome = run_investigation(case_pk=self.case.pk, mode="work", actor_id=self.analyst.pk)
        self.assertEqual(outcome["degraded"], [])
        self.case.refresh_from_db()
        self.assertEqual(self.case.severity_ai, "High")


class AskAgentTests(APITestCase):
    """ask_agent: mode plumbing, history trimming, roles, model-down UX."""

    def setUp(self):
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.analyst.chat_mode = "super_introvert"
        self.analyst.save(update_fields=["chat_mode"])
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)
        self.case = Case.objects.create(title="Ask case", severity="High", description="beaconing")

    def _patch_ask_engine(self):
        eng = mock.Mock()
        eng.complete.return_value = "  The beacon points to 10.0.0.5.  "
        return mock.patch("apps.agents.ask.local_engine", new=eng), eng

    def test_ask_returns_answer_and_passes_callers_mode(self):
        self.client.login(username="ana", password="analyst-pass-123")
        eng_patch, eng = self._patch_ask_engine()
        with eng_patch, mock.patch("apps.agents.views.health_check", return_value=_health_ok()), \
                mock.patch("apps.knowledge.retrieval.propose_keywords", return_value=["beacon"]):
            resp = self.client.post(
                f"/api/cases/{self.case.pk}/ask/",
                {"question": "Where does it beacon to?"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["answer"], "The beacon points to 10.0.0.5.")
        self.assertEqual(resp.data["mode"], "super_introvert")

        kwargs = eng.complete.call_args.kwargs
        self.assertEqual(kwargs["mode"], "super_introvert")
        messages = eng.complete.call_args.args[0]
        self.assertIn("Ask case", messages[0]["content"])  # case context first
        self.assertEqual(messages[-1]["content"], "Where does it beacon to?")

    def test_history_is_trimmed_and_typed(self):
        self.client.login(username="ana", password="analyst-pass-123")
        eng_patch, eng = self._patch_ask_engine()
        long_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(20)]
        with eng_patch, mock.patch("apps.agents.views.health_check", return_value=_health_ok()), \
                mock.patch("apps.knowledge.retrieval.propose_keywords", return_value=[]):
            resp = self.client.post(
                f"/api/cases/{self.case.pk}/ask/",
                {"question": "summarize", "history": long_history},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        messages = eng.complete.call_args.args[0]
        # 1 context + last 8 history + 1 question (system is added via kwarg)
        self.assertEqual(len(messages), 10)
        self.assertEqual(messages[-2]["content"], "turn 19")
        self.assertNotIn({"role": "user", "content": "turn 0"}, messages)

    def test_empty_question_400(self):
        self.client.login(username="ana", password="analyst-pass-123")
        with mock.patch("apps.agents.views.health_check", return_value=_health_ok()):
            resp = self.client.post(f"/api/cases/{self.case.pk}/ask/", {"question": "  "}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_viewer_cannot_ask(self):
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.post(f"/api/cases/{self.case.pk}/ask/", {"question": "hi"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_model_down_returns_503_with_banner(self):
        self.client.login(username="ana", password="analyst-pass-123")
        with mock.patch("apps.agents.views.health_check", return_value=_health_down()):
            resp = self.client.post(f"/api/cases/{self.case.pk}/ask/", {"question": "hi"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("Local model server not detected", resp.data["detail"])

    def test_bad_history_type_400(self):
        self.client.login(username="ana", password="analyst-pass-123")
        with mock.patch("apps.agents.views.health_check", return_value=_health_ok()):
            resp = self.client.post(
                f"/api/cases/{self.case.pk}/ask/", {"question": "x", "history": "nope"}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
