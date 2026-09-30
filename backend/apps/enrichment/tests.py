"""Enrichment tests: regex IOC extraction, local feed provider, API, roles."""

from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.alerts.models import Alert
from apps.cases.models import Case

from .iocs import classify, extract_iocs
from .models import Enrichment, EnrichmentProvider
from .providers import HttpLookupProvider, LocalFeedProvider, ProviderLookupError
from .services import ensure_default_provider, enrich_case


class IocExtractionTests(APITestCase):
    def test_extracts_ips_domains_hashes_urls_emails(self):
        text = (
            "Login from 192.168.1.50 to update-check.example, C2 45.61.136.202, "
            "md5 d41d8cd98f00b204e9800998ecf8427e, url http://evil.example/path, "
            "contact admin@corp.example and again 192.168.1.50"
        )
        iocs = extract_iocs(text)
        values = [i["value"] for i in iocs]
        self.assertIn("192.168.1.50", values)
        self.assertEqual(values.count("192.168.1.50"), 1)  # deduped
        self.assertIn("update-check.example", values)
        self.assertIn("d41d8cd98f00b204e9800998ecf8427e", values)
        self.assertIn("http://evil.example/path", values)
        self.assertIn("admin@corp.example", values)
        types = {i["value"]: i["type"] for i in iocs}
        self.assertEqual(types["192.168.1.50"], "ip")
        self.assertEqual(types["d41d8cd98f00b204e9800998ecf8427e"], "md5")
        self.assertEqual(types["http://evil.example/path"], "url")

    def test_rejects_invalid_ip(self):
        self.assertEqual([i for i in extract_iocs("bad 999.999.999.999")], [])

    def test_classify_shapes(self):
        self.assertEqual(classify("1.2.3.4"), "ip")
        self.assertEqual(classify("example.com"), "domain")
        self.assertEqual(classify("a" * 64), "sha256")

    def test_alert_save_fills_iocs(self):
        alert = Alert.objects.create(title="Beacon from 10.0.0.5", desc="hit evil-payload.example")
        self.assertIn({"type": "ip", "value": "10.0.0.5"}, alert.iocs)
        self.assertIn({"type": "domain", "value": "evil-payload.example"}, alert.iocs)


class ProviderTests(APITestCase):
    def test_local_feed_hits_and_misses(self):
        provider = LocalFeedProvider({"path": str(ensure_default_provider().config["path"])})
        hit = provider.lookup("10.0.0.5")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["verdict"], "malicious")
        self.assertIsNone(provider.lookup("203.0.113.250"))

    def test_local_feed_missing_file_raises(self):
        with self.assertRaises(ProviderLookupError):
            LocalFeedProvider({"path": "nope/missing.csv"}).lookup("1.2.3.4")

    def test_http_provider_parses_verdict_path(self):
        client = mock.Mock()
        response = mock.Mock(status_code=200)
        response.json.return_value = {"data": {"threat_level": "malicious"}}
        client.__enter__ = mock.Mock(return_value=client)
        client.__exit__ = mock.Mock(return_value=False)
        client.get.return_value = response
        provider = HttpLookupProvider(
            {"url_template": "http://misp.local/ioc/{value}", "verdict_path": "data.threat_level"}
        )
        with mock.patch("apps.enrichment.providers.httpx.Client", return_value=client):
            hit = provider.lookup("9.9.9.9")
        self.assertEqual(hit["verdict"], "malicious")

    def test_http_provider_404_is_none(self):
        client = mock.Mock()
        client.__enter__ = mock.Mock(return_value=client)
        client.__exit__ = mock.Mock(return_value=False)
        client.get.return_value = mock.Mock(status_code=404)
        provider = HttpLookupProvider({"url_template": "http://misp.local/ioc/{value}"})
        with mock.patch("apps.enrichment.providers.httpx.Client", return_value=client):
            self.assertIsNone(provider.lookup("9.9.9.9"))


class EnrichmentApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="admin-pass-123", role=User.Role.ADMIN)
        self.analyst = User.objects.create_user("ana", password="analyst-pass-123", role=User.Role.ANALYST)
        self.viewer = User.objects.create_user("vie", password="viewer-pass-123", role=User.Role.VIEWER)
        self.case = Case.objects.create(title="Beacon case", severity="High")
        Alert.objects.create(title="C2 from 10.0.0.5", case=self.case)

    def test_case_enrich_persists_local_feed_verdicts(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post(f"/api/cases/{self.case.pk}/enrich/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(len(resp.data["iocs"]), 1)
        row = Enrichment.objects.get(ioc_value="10.0.0.5")
        self.assertEqual(row.verdict, "malicious")
        self.assertEqual(row.provider, "local_reputation")
        self.assertEqual(resp.data["results"][0]["verdict"], "malicious")

    def test_provider_list_seeds_default_local_feed(self):
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.get("/api/enrichment/providers/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [p["name"] for p in resp.data["results"]]
        self.assertIn("local_reputation", names)

    def test_provider_create_admin_only_and_validation(self):
        self.client.login(username="ana", password="analyst-pass-123")
        resp = self.client.post(
            "/api/enrichment/providers/",
            {"name": "my-misp", "kind": "http_lookup", "config": {"url_template": "http://x/{value}"}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="adm", password="admin-pass-123")
        bad = self.client.post(
            "/api/enrichment/providers/",
            {"name": "bad", "kind": "http_lookup", "config": {"url_template": "http://x/"}},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        good = self.client.post(
            "/api/enrichment/providers/",
            {"name": "my-misp", "kind": "http_lookup", "config": {"url_template": "http://misp.local/{value}"}},
            format="json",
        )
        self.assertEqual(good.status_code, status.HTTP_201_CREATED, good.data)

    def test_enrichment_results_query(self):
        enrich_case(self.case)
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.get("/api/enrichment/?q=10.0.0.5")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"][0]["ioc_value"], "10.0.0.5")

    def test_viewer_cannot_enrich(self):
        self.client.login(username="vie", password="viewer-pass-123")
        resp = self.client.post(f"/api/cases/{self.case.pk}/enrich/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
