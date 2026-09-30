"""Auth + preferences API tests (local login, roles, chat-mode persistence)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from llm import chat_modes

from .models import User


class AuthApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", role=User.Role.ADMIN)
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)

    def test_login_logout_me(self):
        resp = self.client.post("/api/auth/login/", {"username": "ana", "password": "analyst-pass-123"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["chat_mode"], "work")

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["username"], "ana")

        out = self.client.post("/api/auth/logout/")
        self.assertEqual(out.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_403_FORBIDDEN)

    def test_login_rejects_bad_credentials(self):
        resp = self.client.post("/api/auth/login/", {"username": "ana", "password": "wrong"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_mode_persists_per_user(self):
        self.client.login(username="ana", password="analyst-pass-123")
        for mode in ("introvert", "super_introvert", "paranoid", "work"):
            resp = self.client.put("/api/auth/me/preferences/", {"chat_mode": mode}, format="json")
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        resp = self.client.put("/api/auth/me/preferences/", {"chat_mode": "zen"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.analyst.refresh_from_db()
        self.assertEqual(self.analyst.chat_mode, "zen")

        # preference is per-user, not global
        self.client.logout()
        self.client.login(username="admin", password="admin-pass-123")
        self.assertEqual(self.client.get("/api/auth/me/").data["chat_mode"], "work")

    def test_invalid_mode_rejected(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.put("/api/auth/me/preferences/", {"chat_mode": "chatty"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modes_endpoint_lists_five(self):
        resp = self.client.get("/api/auth/modes/")
        self.assertEqual(len(resp.data["modes"]), 5)
        self.assertEqual(resp.data["default"], chat_modes.DEFAULT_MODE)

    def test_first_run_default_mode_is_work(self):
        fresh = User.objects.create_user("newbie", password="password-123")
        self.assertEqual(fresh.chat_mode, "work")
