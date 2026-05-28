"""Tests for DNSService."""
import os
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from ..models import DNSProviderConfig
from ..providers.cloudflare import CloudflareProvider
from ..providers.digitalocean import DigitalOceanProvider
from ..providers.porkbun import PorkbunProvider
from ..services import PROVIDER_MAP, DNSService


def create_unmanaged_table(model: type) -> None:
    from unittest.mock import patch as _patch
    with _patch.object(model._meta, "managed", True), \
         connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.create_model(model)


def drop_unmanaged_table(model: type) -> None:
    from unittest.mock import patch as _patch
    with _patch.object(model._meta, "managed", True), \
         connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.delete_model(model)


class PROVIDER_MAPTests(SimpleTestCase):
    def test_provider_map_keys(self) -> None:
        self.assertSetEqual(set(PROVIDER_MAP.keys()), {"cloudflare", "porkbun", "digitalocean"})

    def test_cloudflare_entry(self) -> None:
        cls, fields, label = PROVIDER_MAP["cloudflare"]
        self.assertIs(cls, CloudflareProvider)
        self.assertEqual(fields, {"api_token"})
        self.assertEqual(label, "API Token")

    def test_porkbun_entry(self) -> None:
        cls, fields, label = PROVIDER_MAP["porkbun"]
        self.assertIs(cls, PorkbunProvider)
        self.assertEqual(fields, {"api_key", "secret_key"})
        self.assertEqual(label, "API Key + Secret Key")

    def test_digitalocean_entry(self) -> None:
        cls, fields, label = PROVIDER_MAP["digitalocean"]
        self.assertIs(cls, DigitalOceanProvider)
        self.assertEqual(fields, {"api_token"})
        self.assertEqual(label, "API Token")


class DNSServiceConfigTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(DNSProviderConfig)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            drop_unmanaged_table(DNSProviderConfig)
        except Exception:
            pass
        super().tearDownClass()

    def _fixture_teardown(self) -> None:
        pass

    def _fixture_setup(self) -> None:
        pass

    def tearDown(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM dns_provider_config")
        super().tearDown()

    def test_get_first_config_none(self) -> None:
        self.assertIsNone(DNSService.get_first_config())

    def test_get_first_config_with_data(self) -> None:
        DNSProviderConfig.objects.create(provider="cloudflare", credentials={"token": "x"})
        DNSProviderConfig.objects.create(provider="porkbun", credentials={"key": "y"})
        cfg = DNSService.get_first_config()
        assert cfg is not None
        self.assertIn(cfg.provider, {"cloudflare", "porkbun"})

    def test_get_config_by_provider_found(self) -> None:
        DNSProviderConfig.objects.create(provider="digitalocean", credentials={"token": "do"})
        cfg = DNSService.get_config_by_provider("digitalocean")
        assert cfg is not None
        self.assertEqual(cfg.provider, "digitalocean")

    def test_get_config_by_provider_not_found(self) -> None:
        self.assertIsNone(DNSService.get_config_by_provider("nonexistent"))

    def test_get_config_by_provider_operational_error(self) -> None:
        class BrokenQuerySet:
            def filter(self, **kwargs):
                return self
            def first(self):
                from django.db.utils import OperationalError
                raise OperationalError("DB down")
        with patch.object(DNSProviderConfig, "objects", BrokenQuerySet()):
            result = DNSService.get_config_by_provider("cloudflare")
            self.assertIsNone(result)

    def test_update_or_create_config_create(self) -> None:
        cfg, created = DNSService.update_or_create_config("porkbun", {"api_key": "pk"})
        self.assertTrue(created)
        self.assertEqual(cfg.provider, "porkbun")
        self.assertEqual(cfg.credentials, {"api_key": "pk"})

    def test_update_or_create_config_update(self) -> None:
        DNSProviderConfig.objects.create(provider="porkbun", credentials={"api_key": "old"})
        cfg, created = DNSService.update_or_create_config("porkbun", {"api_key": "new"})
        self.assertFalse(created)
        self.assertEqual(cfg.credentials["api_key"], "new")

    def test_get_provider_returns_instance(self) -> None:
        DNSProviderConfig.objects.create(
            provider="cloudflare", credentials={"api_token": "cf_token"}
        )
        provider = DNSService.get_provider("cloudflare")
        assert provider is not None
        self.assertIsInstance(provider, CloudflareProvider)

    def test_get_provider_none_when_no_config(self) -> None:
        self.assertIsNone(DNSService.get_provider("cloudflare"))


class DNSServiceServerIPTests(SimpleTestCase):
    def setUp(self) -> None:
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()

    @patch("requests.get")
    def test_get_server_ip_public(self, mock_get: MagicMock) -> None:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "203.0.113.42"
        ip = DNSService.get_server_ip()
        self.assertEqual(ip, "203.0.113.42")

    @patch("requests.get")
    def test_get_server_ip_private_fallback_to_hostname(self, mock_get: MagicMock) -> None:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "10.0.0.1"
        with patch.dict(os.environ, {"MAIL_HOSTNAME": "mail.example.com"}):
            with patch("socket.gethostbyname", return_value="198.51.100.10"):
                ip = DNSService.get_server_ip()
                self.assertEqual(ip, "198.51.100.10")

    @patch("requests.get")
    def test_get_server_ip_all_fail(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("Network error")
        with patch("socket.gethostbyname", side_effect=Exception("DNS fail")):
            ip = DNSService.get_server_ip()
            self.assertEqual(ip, "0.0.0.0")


class DNSServiceBuildRecordsTests(SimpleTestCase):
    def setUp(self) -> None:
        self.env_patcher = patch.dict(os.environ, {
            "MAIL_HOSTNAME": "mail.ifinmail.test",
            "DKIM_SELECTOR": "default",
        }, clear=True)
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()

    def test_build_records_returns_eight_records(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        self.assertEqual(len(records), 8)

    def test_build_records_a_records(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        a_records = [r for r in records if r.type == "A"]
        self.assertEqual(len(a_records), 3)
        names = {r.name for r in a_records}
        self.assertEqual(names, {"@", "mail", "mta-sts"})

    def test_build_records_mx(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        mx = next(r for r in records if r.type == "MX")
        self.assertEqual(mx.name, "@")
        self.assertEqual(mx.value, "mail.ifinmail.test")
        self.assertEqual(mx.priority, 10)

    def test_build_records_spf(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        spf = next(r for r in records if r.type == "TXT" and r.name == "@")
        self.assertEqual(spf.value, "v=spf1 mx -all")

    def test_build_records_dmarc(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        dmarc = next(r for r in records if r.type == "TXT" and r.name == "_dmarc")
        self.assertIn("v=DMARC1", dmarc.value)
        self.assertIn("postmaster@example.com", dmarc.value)

    def test_build_records_mta_sts(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        mta_sts = next(r for r in records if r.type == "TXT" and r.name == "_mta-sts")
        self.assertIn("v=STSv1", mta_sts.value)
        self.assertIn("id=", mta_sts.value)

    def test_build_records_dkim_default(self) -> None:
        records = DNSService.build_records("example.com", "203.0.113.42")
        dkim = next(r for r in records if r.type == "TXT" and "_domainkey" in r.name)
        self.assertEqual(dkim.name, "default._domainkey")
        self.assertIn("p=<add-dkim-key>", dkim.value)

    @patch("os.path.isfile", return_value=True)
    @patch("builtins.open")
    def test_build_records_dkim_with_key(self, mock_open: MagicMock, mock_isfile: MagicMock) -> None:
        mock_open.return_value.__enter__.return_value = ["-----BEGIN PUBLIC KEY-----\n", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n", "-----END PUBLIC KEY-----\n"]
        records = DNSService.build_records("example.com", "203.0.113.42")
        dkim = next(r for r in records if r.type == "TXT" and "_domainkey" in r.name)
        self.assertNotIn("<add-dkim-key>", dkim.value)
        self.assertIn("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA", dkim.value)
