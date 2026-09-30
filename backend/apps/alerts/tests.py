"""Alert ingestion + query API tests."""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.cases.models import Case

from .models import Alert, Severity


class AlertApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", role=User.Role.ADMIN)
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)

    def test_requires_login(self):
        resp = self.client.get("/api/alerts/")
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_viewer_reads_but_cannot_create(self):
        self.client.login(username="vie", password="viewer-pass-123")
        self.assertEqual(self.client.get("/api/alerts/").status_code, status.HTTP_200_OK)
        resp = self.client.post("/api/alerts/", {"title": "nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_single_create_assigns_readable_id_and_normalizes_severity(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post(
            "/api/alerts/",
            {"title": "Brute force", "severity": "CRITICAL", "rule_id": "r-1", "correlation_uid": "corr-9"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["alert_id"], "alert_000001")
        self.assertEqual(resp.data["severity"], "Critical")
        self.assertEqual(resp.data["source"], "webhook")
        self.assertEqual(resp.data["status"], "New")

    def test_batch_ingest_partial_success(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post(
            "/api/alerts/",
            {
                "source": "siem",
                "alerts": [
                    {"title": "A1", "severity": "high"},
                    {"title": "A2", "correlation_uid": "corr-1"},
                    "not-an-object",
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["created"], 2)
        self.assertEqual(len(resp.data["errors"]), 1)
        self.assertEqual(Alert.objects.get(title="A2").source, "siem")
        self.assertEqual(
            list(Alert.objects.filter(correlation_uid="corr-1").values_list("title", flat=True)), ["A2"]
        )
        self.assertTrue(AuditLog.objects.filter(action="ingest").exists())

    def test_filters(self):
        self.client.login(username="ana", password="analyst-pass-123")
        Case.objects.create(title="c1")
        self.client.post("/api/alerts/", {"alerts": [
            {"title": "phish", "severity": "medium", "correlation_uid": "x"},
            {"title": "malware", "severity": "high", "correlation_uid": "y"},
        ]}, format="json")
        resp = self.client.get("/api/alerts/?correlation_uid=x")
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["title"], "phish")
        resp = self.client.get("/api/alerts/?severity=High")
        self.assertEqual(resp.data["count"], 1)
        resp = self.client.get("/api/alerts/?q=malw")
        self.assertEqual(resp.data["count"], 1)
        resp = self.client.get("/api/alerts/?orphan=1")
        self.assertEqual(resp.data["count"], 2)

    def test_patch_status_updates_and_audits(self):
        alert = Alert.objects.create(title="t", severity=Severity.LOW)
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.patch(f"/api/alerts/{alert.pk}/", {"status": "in progress"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        alert.refresh_from_db()
        self.assertEqual(alert.status, "In Progress")
        log = AuditLog.objects.filter(action="update").first()
        self.assertIsNotNone(log)
        self.assertIn("status", log.changes)

    def test_viewer_cannot_patch(self):
        alert = Alert.objects.create(title="t")
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.patch(f"/api/alerts/{alert.pk}/", {"status": "Resolved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_alert_links_to_case_in_payload(self):
        case = Case.objects.create(title="case-a")
        alert = Alert.objects.create(title="t", case=case)
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.get(f"/api/alerts/{alert.pk}/")
        self.assertEqual(resp.data["case_id_ref"]["case_id"], case.case_id)
