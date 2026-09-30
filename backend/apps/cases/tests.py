"""Case CRUD, alert linking, and timeline tests."""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.alerts.models import Alert
from apps.audit.models import AuditLog

from .models import Case, CaseEvent, CaseStatus


class CaseApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", role=User.Role.ADMIN)
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)

    def test_requires_login(self):
        resp = self.client.get("/api/cases/")
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_create_assigns_id_and_timeline(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post("/api/cases/", {"title": "Suspicious login"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["case_id"], "case_000001")
        self.assertEqual(resp.data["status"], "New")
        case = Case.objects.get(pk=resp.data["id"])
        self.assertTrue(CaseEvent.objects.filter(case=case, kind="system").exists())
        self.assertTrue(AuditLog.objects.filter(action="create").exists())

    def test_viewer_cannot_create(self):
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.post("/api/cases/", {"title": "nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_counts_alerts_and_filters(self):
        self.client.login(username="ana", password="analyst-pass-123")
        c1 = Case.objects.create(title="with alerts")
        Case.objects.create(title="empty", status=CaseStatus.CLOSED)
        Alert.objects.create(title="a1", case=c1)
        Alert.objects.create(title="a2", case=c1)
        resp = self.client.get("/api/cases/")
        self.assertEqual(resp.data["count"], 2)
        by_id = {r["case_id"]: r for r in resp.data["results"]}
        self.assertEqual(by_id["case_000001"]["alert_count"], 2)
        self.assertEqual(by_id["case_000002"]["alert_count"], 0)
        resp = self.client.get("/api/cases/?status=Closed")
        self.assertEqual(resp.data["count"], 1)
        resp = self.client.get("/api/cases/?q=with")
        self.assertEqual(resp.data["count"], 1)

    def test_link_alerts_and_detail_nested(self):
        self.client.login(username="ana", password="analyst-pass-123")
        case = Case.objects.create(title="corr case")
        a1 = Alert.objects.create(title="a1")
        a2 = Alert.objects.create(title="a2")
        resp = self.client.post(f"/api/cases/{case.pk}/alerts/", {"alert_ids": [a1.pk, a2.pk]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["linked"], 2)

        a1.refresh_from_db()
        self.assertEqual(a1.case_id, case.pk)
        self.assertTrue(CaseEvent.objects.filter(case=case, kind="link").exists())

        detail = self.client.get(f"/api/cases/{case.pk}/").data
        self.assertEqual(len(detail["alerts"]), 2)
        self.assertEqual(detail["alert_count"], 2)
        self.assertTrue(any(e["kind"] == "link" for e in detail["events"]))

    def test_link_rejects_unknown_alerts(self):
        self.client.login(username="ana", password="analyst-pass-123")
        case = Case.objects.create(title="c")
        resp = self.client.post(f"/api/cases/{case.pk}/alerts/", {"alert_ids": [999]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_change_writes_timeline_and_audit_and_closes_time(self):
        self.client.login(username="ana", password="analyst-pass-123")
        case = Case.objects.create(title="c")
        resp = self.client.patch(
            f"/api/cases/{case.pk}/", {"status": "Resolved", "severity": "high"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        case.refresh_from_db()
        self.assertEqual(case.severity, "High")
        self.assertIsNotNone(case.closed_time)
        self.assertTrue(CaseEvent.objects.filter(case=case, kind="status").exists())
        log = AuditLog.objects.filter(action="update").first()
        self.assertIn("status", log.changes)
        self.assertIn("severity", log.changes)

    def test_assignee_by_username(self):
        self.client.login(username="ana", password="analyst-pass-123")
        case = Case.objects.create(title="c")
        resp = self.client.patch(f"/api/cases/{case.pk}/", {"assignee": "ana"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        case.refresh_from_db()
        self.assertEqual(case.assignee.username, "ana")
        detail = self.client.get(f"/api/cases/{case.pk}/").data
        self.assertEqual(detail["assignee"], "ana")

    def test_delete_records_audit(self):
        self.client.login(username="admin", password="admin-pass-123")
        case = Case.objects.create(title="doomed")
        resp = self.client.delete(f"/api/cases/{case.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Case.objects.filter(pk=case.pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="delete", metadata__case_id=case.case_id).exists()
        )
