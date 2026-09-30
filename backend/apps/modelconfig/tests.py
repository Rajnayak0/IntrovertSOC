"""Model status/config API tests - including the "llamafile is down" UX contract."""

from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import ModelConfig


class ModelConfigApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", role=User.Role.ADMIN)
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)

    def test_status_requires_login(self):
        resp = self.client.get("/api/model/status/")
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_status_banner_when_server_down(self):
        self.client.login(username="vie", password="viewer-pass-123")
        with mock.patch("llm.health._probe") as probe:
            probe.return_value = mock.Mock(
                ok=False,
                base_url="http://127.0.0.1:8080",
                detail="ConnectRefused",
                server_model=None,
                latency_ms=2,
                checked_at=0.0,
                as_dict=lambda: {},
            )
            resp = self.client.get("/api/model/status/?force=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["connected"])
        self.assertIn("Local model server not detected", resp.data["banner"])
        self.assertIn("start your llamafile", resp.data["banner"])

    def test_config_readable_by_anyone_editable_by_admin_only(self):
        self.client.login(username="vie", password="viewer-pass-123")
        self.assertEqual(self.client.get("/api/model/config/").status_code, status.HTTP_200_OK)
        denied = self.client.put("/api/model/config/", {"model": "x"}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="admin", password="admin-pass-123")
        resp = self.client.put(
            "/api/model/config/",
            {"base_url": "http://127.0.0.1:9099", "model": "my-q4-model", "gguf_path": "D:/models/x.gguf"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        row = ModelConfig.get_solo()
        self.assertEqual(row.model, "my-q4-model")
        self.assertEqual(row.updated_by, "admin")

        cfg = self.client.get("/api/model/config/").data
        self.assertEqual(cfg["effective"]["base_url"], "http://127.0.0.1:9099")
        self.assertEqual(cfg["source"], "db")
        self.assertIn("llamafile", cfg["launch_commands"]["windows"])

    def test_config_rejects_non_http_base_url(self):
        self.client.login(username="admin", password="admin-pass-123")
        resp = self.client.put("/api/model/config/", {"base_url": "ftp://nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_api_key_field_anywhere_in_config_payload(self):
        self.client.login(username="admin", password="admin-pass-123")
        resp = self.client.get("/api/model/config/")
        blob = str(resp.data).lower()
        self.assertNotIn("api_key", blob)
        self.assertNotIn("apikey", blob)
        self.assertNotIn("token", blob)

    def test_context_window_roundtrip_and_auto_default(self):
        self.client.login(username="admin", password="admin-pass-123")

        resp = self.client.put("/api/model/config/", {"context_window": 131072}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(self.client.get("/api/model/config/").data["override"]["context_window"], 131072)
        self.assertEqual(ModelConfig.get_solo().context_window, 131072)

        from llm import adapter

        self.assertEqual(adapter.context_info(), (131072, "override"))
        self.assertTrue(adapter.wants_inline_kb())

        # 0 = auto -> falls back to the server-reported (or default) window
        self.client.put("/api/model/config/", {"context_window": 0}, format="json")
        with mock.patch("llm.adapter.health_check") as hc:
            hc.return_value = mock.Mock(context_length=262144)
            self.assertEqual(adapter.context_info(), (262144, "server"))
        self.assertEqual(ModelConfig.get_solo().context_window, 0)

    def test_context_window_rejects_garbage_and_clamps(self):
        self.client.login(username="admin", password="admin-pass-123")
        bad = self.client.put("/api/model/config/", {"context_window": "lots"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        from llm import adapter

        resp = self.client.put(
            "/api/model/config/", {"context_window": 99999999}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(ModelConfig.get_solo().context_window, adapter.MAX_CONTEXT_WINDOW)

    def test_status_payload_exposes_family_and_context(self):
        self.client.login(username="vie", password="viewer-pass-123")
        with mock.patch("llm.health._probe") as probe:
            probe.return_value = mock.Mock(
                ok=True,
                base_url="http://127.0.0.1:8080",
                detail="ok",
                server_model="MiMo-V2.6-Flash-RL",
                latency_ms=5,
                checked_at=0.0,
                context_length=1048576,
                as_dict=lambda: {},
            )
            resp = self.client.get("/api/model/status/?force=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["family"], "mimo")
        self.assertEqual(resp.data["context_window"], 1048576)
        self.assertIn(resp.data["context_source"], ("server", "override", "default"))
