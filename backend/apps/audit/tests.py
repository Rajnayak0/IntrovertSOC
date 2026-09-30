"""Audit trail tests: recording + admin-only read."""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.modelconfig.models import ModelConfig

from .models import AuditLog, record


class AuditApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", role=User.Role.ADMIN)
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)

    def test_login_and_logout_are_recorded(self):
        resp = self.client.post("/api/auth/login/", {"username": "ana", "password": "analyst-pass-123"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        login_log = AuditLog.objects.filter(action="login").first()
        self.assertIsNotNone(login_log)
        self.assertEqual(login_log.actor.username, "ana")
        self.assertIsNone(login_log.content_type)

        self.client.post("/api/auth/logout/")
        self.assertTrue(AuditLog.objects.filter(action="logout", actor=self.analyst).exists())

    def test_record_ties_object_to_content_type(self):
        row = ModelConfig.get_or_create_solo()
        log = record("update", obj=row, actor=self.admin, changes={"model": "x"})
        self.assertEqual(log.content_type.model, "modelconfig")
        self.assertEqual(log.object_id, str(row.pk))

    def test_list_admin_only(self):
        record("update", obj=None, actor=self.admin)
        self.client.login(username="ana", password="analyst-pass-123")
        self.assertEqual(self.client.get("/api/audit/").status_code, status.HTTP_403_FORBIDDEN)
        self.client.logout()
        self.client.login(username="admin", password="admin-pass-123")
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_action_filter(self):
        record("create", obj=None, actor=self.admin)
        record("delete", obj=None, actor=self.admin)
        self.client.login(username="admin", password="admin-pass-123")
        resp = self.client.get("/api/audit/?action=delete")
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["action"], "delete")
