"""Dashboard stats endpoint tests."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.alerts.models import Alert
from apps.cases.models import Case, CaseStatus


class DashboardStatsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)

    def test_requires_login(self):
        resp = self.client.get("/api/dashboard/")
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_counts_and_recency(self):
        Alert.objects.create(title="old", severity="High")
        fresh = Alert.objects.create(title="new", severity="Critical")
        # backdate one alert beyond 24h
        Alert.objects.filter(pk=fresh.pk).update(created_at=timezone.now() - timedelta(hours=30))
        Alert.objects.create(title="recent", severity="Critical")

        Case.objects.create(title="open case")
        Case.objects.create(title="done case", status=CaseStatus.CLOSED)

        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.get("/api/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        self.assertEqual(resp.data["alerts"]["total"], 3)
        self.assertEqual(resp.data["alerts"]["last_24h"], 2)
        self.assertEqual(resp.data["alerts"]["unassigned"], 3)
        self.assertEqual(resp.data["alerts"]["by_severity"]["Critical"], 2)
        self.assertEqual(resp.data["cases"]["total"], 2)
        self.assertEqual(resp.data["cases"]["open"], 1)
        self.assertEqual(len(resp.data["recent_alerts"]), 3)
        self.assertEqual(len(resp.data["recent_cases"]), 2)
        self.assertIn("alert_count", resp.data["recent_cases"][0])
