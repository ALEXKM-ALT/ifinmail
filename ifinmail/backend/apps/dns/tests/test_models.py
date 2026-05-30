"""Tests for DNSProviderConfig model."""

from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from ..models import DNSProviderConfig


def create_unmanaged_table(model: type) -> None:
    with (
        patch.object(model._meta, 'managed', True),
        connection.schema_editor(atomic=False) as schema_editor,
    ):
        schema_editor.create_model(model)


def drop_unmanaged_table(model: type) -> None:
    with (
        patch.object(model._meta, 'managed', True),
        connection.schema_editor(atomic=False) as schema_editor,
    ):
        schema_editor.delete_model(model)


class DNSProviderConfigStrTests(SimpleTestCase):
    def test_str_cloudflare(self) -> None:
        cfg = DNSProviderConfig(provider='cloudflare')
        self.assertEqual(str(cfg), 'DNS: cloudflare')

    def test_str_porkbun(self) -> None:
        cfg = DNSProviderConfig(provider='porkbun')
        self.assertEqual(str(cfg), 'DNS: porkbun')

    def test_str_digitalocean(self) -> None:
        cfg = DNSProviderConfig(provider='digitalocean')
        self.assertEqual(str(cfg), 'DNS: digitalocean')


class DNSProviderConfigMetaTests(SimpleTestCase):
    def test_db_table(self) -> None:
        self.assertEqual(DNSProviderConfig._meta.db_table, 'dns_provider_config')

    def test_managed(self) -> None:
        self.assertFalse(DNSProviderConfig._meta.managed)


class DNSProviderConfigFieldTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(DNSProviderConfig)

    @classmethod
    def tearDownClass(cls) -> None:
        import contextlib

        with contextlib.suppress(Exception):
            drop_unmanaged_table(DNSProviderConfig)
        super().tearDownClass()

    def _fixture_teardown(self=None) -> None:
        pass

    def _fixture_setup(self=None) -> None:
        pass

    def tearDown(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM dns_provider_config')
        super().tearDown()

    def test_credentials_default(self) -> None:
        cfg = DNSProviderConfig.objects.create(provider='cloudflare')
        self.assertEqual(cfg.credentials, {})

    def test_provider_unique(self) -> None:
        from django.db import IntegrityError

        DNSProviderConfig.objects.create(provider='cloudflare', credentials={'token': 'abc'})
        with self.assertRaises(IntegrityError):
            DNSProviderConfig.objects.create(provider='cloudflare', credentials={'token': 'def'})

    def test_provider_choices_valid(self) -> None:
        for choice in ('cloudflare', 'porkbun', 'digitalocean'):
            with self.subTest(provider=choice):
                cfg = DNSProviderConfig.objects.create(provider=choice)
                self.assertEqual(cfg.provider, choice)

    def test_create_with_credentials(self) -> None:
        cfg = DNSProviderConfig.objects.create(
            provider='digitalocean',
            credentials={'api_token': 'do_token_123'},
        )
        self.assertEqual(cfg.credentials['api_token'], 'do_token_123')

    def test_update_credentials(self) -> None:
        cfg = DNSProviderConfig.objects.create(provider='porkbun', credentials={'api_key': 'old'})
        cfg.credentials['api_key'] = 'new'
        cfg.save()
        cfg.refresh_from_db()
        self.assertEqual(cfg.credentials['api_key'], 'new')
