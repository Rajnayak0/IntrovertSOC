"""Playbook tests: built-in seeding, synchronous runs, degraded steps, roles, polling API."""

from unittest import mock

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.cases.models import Case
from llm.schemas import LLMUnavailable

from .builtins import sync_builtins
from .models import Playbook, PlaybookRun

SYNC = override_settings(PLAYBOOKS_SYNC=True)


class BuiltinSyncTests(APITestCase):
    def test_sync_seeds_shipped_playbooks(self):
        created = sync_builtins()
        self.assertGreaterEqual(created, 4)
        names = set(Playbook.objects.values_list("name", flat=True))
        self.assertTrue({"case_summary", "investigate", "extract_knowledge", "triage_and_learn"} <= names)
        summary = Playbook.objects.get(name="case_summary")
        self.assertTrue(summary.builtin)
        self.assertIn("llm", summary.definition)
        # idempotent
        self.assertEqual(sync_builtins(), 0)

    def test_list_endpoint_lazy_seeds(self):
        self.assertEqual(Playbook.objects.count(), 0)
        user = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.get("/api/playbooks/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertGreaterEqual(len(resp.data["results"]), 4)


@SYNC
class RunTests(APITestCase):
    def setUp(self):
        self.analyst = User.objects.create_user(
            "ana", password="analyst-pass-123", role=User.Role.ANALYST, chat_mode="introvert"
        )
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)
        self.admin = User.objects.create_user("adm", password="admin-pass-123", role=User.Role.ADMIN)
        self.case = Case.objects.create(title="Play case", severity="High")

    def _run(self, playbook, data=None, user="ana", password="analyst-pass-123"):
        self.client.login(username=user, password=password)
        return self.client.post(f"/api/playbooks/{playbook.pk}/run/", data or {}, format="json")

    def test_llm_step_uses_requesters_mode(self):
        pb = Playbook.objects.create(
            name="sum", description="d", definition="steps:\n  - type: llm\n    prompt: 'Summarize {{case}}'\n"
        )
        engine = mock.Mock()
        engine.complete.return_value = "One paragraph summary."
        with mock.patch("apps.playbooks.runner.local_engine", new=engine):
            resp = self._run(pb, {"case_id": self.case.pk})
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertEqual(resp.data["status"], "succeeded")
        self.assertEqual(resp.data["steps"][0]["status"], "ok")
        self.assertIn("One paragraph summary", resp.data["steps"][0]["detail"])
        self.assertEqual(engine.complete.call_args.kwargs["mode"], "introvert")

    def test_llm_step_requires_case(self):
        pb = Playbook.objects.create(name="nocase", definition="steps:\n  - type: llm\n    prompt: hi\n")
        engine = mock.Mock()
        with mock.patch("apps.playbooks.runner.local_engine", new=engine):
            resp = self._run(pb, {})
        self.assertEqual(resp.data["status"], "degraded")
        self.assertEqual(resp.data["steps"][0]["status"], "error")
        self.assertIn("requires a case", resp.data["steps"][0]["detail"])
        engine.complete.assert_not_called()

    def test_llm_step_degrades_on_model_down(self):
        pb = Playbook.objects.create(name="down", definition="steps:\n  - type: llm\n    prompt: hi\n")
        engine = mock.Mock()
        engine.complete.side_effect = LLMUnavailable("refused")
        with mock.patch("apps.playbooks.runner.local_engine", new=engine):
            resp = self._run(pb, {"case_id": self.case.pk})
        self.assertEqual(resp.data["status"], "degraded")
        self.assertIn("model unavailable", resp.data["steps"][0]["detail"])

    def test_investigate_step_delegates_to_shared_service(self):
        pb = Playbook.objects.create(name="inv", definition="steps:\n  - type: investigate\n")
        with mock.patch("apps.playbooks.runner.run_investigation") as inv:
            inv.return_value = {"degraded": [], "ms": 5}
            resp = self._run(pb, {"case_id": self.case.pk})
        inv.assert_called_once_with(case_pk=self.case.pk, mode="introvert", actor_id=self.analyst.pk)
        self.assertEqual(resp.data["status"], "succeeded")

    def test_log_step_runs_without_case(self):
        pb = Playbook.objects.create(
            name="lg", definition="steps:\n  - type: log\n    message: hello\n"
        )
        resp = self._run(pb, {})
        self.assertEqual(resp.data["status"], "succeeded")
        self.assertEqual(resp.data["steps"][0]["detail"], "hello")

    def test_run_detail_polling_shape(self):
        pb = Playbook.objects.create(name="poll", definition="steps:\n  - type: log\n    message: x\n")
        self._run(pb, {})
        run_id = PlaybookRun.objects.get().pk
        resp = self.client.get(f"/api/playbooks/runs/{run_id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("status", "steps", "mode", "started_at", "finished_at", "playbook"):
            self.assertIn(key, resp.data)

    def test_viewer_cannot_run(self):
        pb = Playbook.objects.create(name="vr", definition="steps:\n  - type: log\n    message: x\n")
        resp = self._run(pb, {}, user="vie", password="viewer-pass-123")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_disabled_playbook_400(self):
        pb = Playbook.objects.create(name="dis", enabled=False, definition="steps:\n  - type: log\n")
        resp = self._run(pb, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_case_404(self):
        pb = Playbook.objects.create(name="nc404", definition="steps:\n  - type: log\n")
        resp = self._run(pb, {"case_id": 9999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class DefinitionApiTests(APITestCase):
    def setUp(self):
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.admin = User.objects.create_user("adm", password="admin-pass-123", role=User.Role.ADMIN)
        self.pb = Playbook.objects.create(name="editable", definition="steps:\n  - type: log\n    message: x\n")

    def test_create_rejects_unknown_step_type(self):
        self.client.login(username="adm", password="admin-pass-123")
        resp = self.client.post(
            "/api/playbooks/",
            {"name": "custom", "definition": "steps:\n  - type: shell\n    cmd: rm /\n"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unknown step", resp.data["detail"])

    def test_create_rejects_bad_yaml(self):
        self.client.login(username="adm", password="admin-pass-123")
        resp = self.client.post(
            "/api/playbooks/", {"name": "bad", "definition": "steps: [unclosed"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_analyst_cannot_create_or_update(self):
        self.client.login(username="ana", password="analyst-pass-123")
        create = self.client.post("/api/playbooks/", {"name": "x", "definition": "steps: []"}, format="json")
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)
        patch = self.client.patch(
            f"/api/playbooks/{self.pb.pk}/", {"description": "changed"}, format="json"
        )
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_updates_definition(self):
        self.client.login(username="adm", password="admin-pass-123")
        resp = self.client.patch(
            f"/api/playbooks/{self.pb.pk}/",
            {"definition": "steps:\n  - type: log\n    message: updated\n"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.pb.refresh_from_db()
        self.assertIn("updated", self.pb.definition)
