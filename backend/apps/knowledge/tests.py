"""Knowledge base tests: extraction on close, retrieval scoring, keyword fallback, API."""

from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.cases.models import Case, CaseStatus
from llm.schemas import LLMUnavailable

from . import extraction
from .models import KnowledgeItem
from .retrieval import KeywordList, context_block, fallback_keywords, propose_keywords, search


class ExtractionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="admin-pass-123", role=User.Role.ADMIN)
        self.case = Case.objects.create(title="Closed brute force case", severity="High")

    def _patch_model_ok(self, items=None):
        engine = mock.Mock()
        from .extraction import KnowledgeExtraction, KnowledgeRecord

        engine.complete_json.return_value = KnowledgeExtraction(
            items=items
            if items is not None
            else [KnowledgeRecord(title="SSH brute-force play", body="Check auth.log.", tags=["ssh"])]
        )
        return mock.patch("apps.knowledge.extraction.local_engine", new=engine)

    def test_extract_creates_items_timeline_and_audit(self):
        from apps.audit.models import AuditLog

        with mock.patch("apps.knowledge.extraction.health_check", return_value=mock.Mock(ok=True)):
            with self._patch_model_ok():
                outcome = extraction.extract_for_case(self.case, actor=self.admin)
        self.assertEqual(outcome["created"], 1)
        self.assertEqual(KnowledgeItem.objects.filter(case=self.case).count(), 1)
        item = KnowledgeItem.objects.get()
        self.assertEqual(item.source, "extraction")
        self.assertEqual(item.tags, ["ssh"])
        self.assertTrue(self.case.events.filter(kind="system", message__icontains="knowledge").exists())
        self.assertTrue(AuditLog.objects.filter(action="create", object_id=str(self.case.pk)).exists())

    def test_extract_skips_gracefully_when_model_down(self):
        with mock.patch("apps.knowledge.extraction.health_check", return_value=mock.Mock(ok=False)):
            outcome = extraction.extract_for_case(self.case, actor=self.admin)
        self.assertIn("skipped", outcome)
        self.assertEqual(KnowledgeItem.objects.count(), 0)

    def test_extract_dedupes_existing_titles(self):
        KnowledgeItem.objects.create(title="SSH brute-force play", body="old")
        with mock.patch("apps.knowledge.extraction.health_check", return_value=mock.Mock(ok=True)):
            with self._patch_model_ok():
                outcome = extraction.extract_for_case(self.case, actor=self.admin)
        self.assertEqual(outcome["created"], 0)
        self.assertEqual(KnowledgeItem.objects.count(), 1)

    def test_close_via_api_triggers_extraction(self):
        self.client.login(username="adm", password="admin-pass-123")
        with mock.patch("apps.knowledge.extraction.extract_for_case") as extractor:
            extractor.return_value = {"created": 1, "titles": ["x"]}
            resp = self.client.patch(
                f"/api/cases/{self.case.pk}/", {"status": CaseStatus.CLOSED}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        extractor.assert_called_once()
        self.assertEqual(extractor.call_args.args[0].pk, self.case.pk)

    def test_resolved_status_does_not_extract(self):
        self.client.login(username="adm", password="admin-pass-123")
        with mock.patch("apps.knowledge.extraction.extract_for_case") as extractor:
            resp = self.client.patch(
                f"/api/cases/{self.case.pk}/", {"status": CaseStatus.RESOLVED}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        extractor.assert_not_called()


class RetrievalTests(APITestCase):
    def setUp(self):
        self.ssh = KnowledgeItem.objects.create(title="SSH brute force playbooks", body="Check auth.log", tags=["ssh"])
        self.dns = KnowledgeItem.objects.create(title="DNS tunneling notes", body="Look for long queries", tags=["dns"])
        self.other = KnowledgeItem.objects.create(title="Unrelated printer issue", body="toner", tags=[])

    def test_search_scores_title_match_higher(self):
        hits = search("ssh brute", top_k=3, keywords=["ssh", "brute"])
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], self.ssh.pk)
        self.assertEqual(len(hits), 1)

    def test_search_without_keywords_is_deterministic(self):
        hits = search("dns tunneling", top_k=3, propose=False)
        self.assertEqual(hits[0]["id"], self.dns.pk)

    def test_multi_word_keywords_expand_to_tokens(self):
        hits = search("ssh brute force prevention", top_k=3, keywords=["ssh brute force prevention"])
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], self.ssh.pk)

    def test_search_no_matches_returns_empty(self):
        self.assertEqual(search("zzzz nothing", top_k=3, keywords=["zzzz"]), [])

    def test_propose_keywords_falls_back_when_model_down(self):
        engine = mock.Mock()
        engine.complete_json.side_effect = LLMUnavailable("down")
        with mock.patch("apps.knowledge.retrieval.local_engine", new=engine):
            words = propose_keywords("lateral movement over smb")
        self.assertTrue(words)
        self.assertIn("lateral", words)

    def test_propose_keywords_uses_model_when_up(self):
        engine = mock.Mock()
        engine.complete_json.return_value = KeywordList(keywords=["kerberoast", "the", "ok"])
        with mock.patch("apps.knowledge.retrieval.local_engine", new=engine):
            words = propose_keywords("kerberoasting?")
        self.assertEqual(words, ["kerberoast"])  # stopword "the" filtered

    def test_fallback_keywords_skip_stopwords(self):
        self.assertEqual(fallback_keywords("the and brute force"), ["brute", "force"])


class ContextBlockTests(APITestCase):
    """Phase 10: adaptive KB - top-K on small models, full inline dump on >=128k."""

    def setUp(self):
        self.ssh = KnowledgeItem.objects.create(title="SSH brute force playbooks", body="Check auth.log", tags=["ssh"])
        self.dns = KnowledgeItem.objects.create(title="DNS tunneling notes", body="Look for long queries", tags=["dns"])
        self.other = KnowledgeItem.objects.create(title="Unrelated printer issue", body="toner", tags=[])

    def test_small_context_uses_topk_not_full_dump(self):
        with mock.patch("apps.knowledge.retrieval.adapter.wants_inline_kb", return_value=False):
            block = context_block("dns tunneling", propose=False)
        self.assertTrue(block.startswith("Relevant knowledge:"))
        self.assertIn("DNS tunneling notes", block)
        self.assertNotIn("Unrelated printer issue", block)

    def test_big_context_inlines_entire_kb(self):
        with mock.patch("apps.knowledge.retrieval.adapter.wants_inline_kb", return_value=True):
            block = context_block("dns tunneling", propose=False)
        self.assertIn("complete - all entries", block)
        self.assertIn("SSH brute force playbooks", block)
        self.assertIn("DNS tunneling notes", block)
        self.assertIn("Unrelated printer issue", block)

    def test_search_api_still_topk_when_inline_blocked(self):
        with mock.patch("apps.knowledge.retrieval.adapter.wants_inline_kb", return_value=False):
            self.assertEqual(search("zzzz nothing", top_k=3, keywords=["zzzz"]), [])


class KnowledgeApiTests(APITestCase):
    def setUp(self):
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)

    def test_create_list_delete_manual_item(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post(
            "/api/knowledge/", {"title": "EDR bypass note", "body": "Watch for unhooking", "tags": ["EDR"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["tags"], ["edr"])  # normalized lowercase
        self.assertEqual(resp.data["source"], "manual")

        listing = self.client.get("/api/knowledge/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)

        delete = self.client.delete(f"/api/knowledge/{resp.data['id']}/")
        self.assertEqual(delete.status_code, status.HTTP_200_OK)
        self.assertEqual(KnowledgeItem.objects.count(), 0)

    def test_create_requires_title(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post("/api/knowledge/", {"body": "x"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_endpoint_degrades_to_fallback(self):
        KnowledgeItem.objects.create(title="Brute force detection", body="fail2ban ideas", tags=[])
        self.client.login(username="ana", password="analyst-pass-123")
        engine = mock.Mock()
        engine.complete_json.side_effect = LLMUnavailable("down")
        with mock.patch("apps.knowledge.retrieval.local_engine", new=engine):
            resp = self.client.get("/api/knowledge/?q=brute+force+detection")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["results"][0]["title"], "Brute force detection")

    def test_viewer_cannot_write(self):
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.post("/api/knowledge/", {"title": "nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_extract_endpoint_unknown_case_404(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post("/api/knowledge/extract/", {"case_id": 9999}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
