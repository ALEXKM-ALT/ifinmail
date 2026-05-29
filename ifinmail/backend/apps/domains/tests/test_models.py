"""Tests for domains models."""

from django.test import TestCase

from ..models import DKIMKey, Domain


class DomainModelTests(TestCase):
    def test_domain_str(self) -> None:
        domain = Domain(name='example.com')
        self.assertEqual(str(domain), 'example.com')

    def test_domain_meta(self) -> None:
        self.assertEqual(Domain._meta.db_table, 'domains')
        self.assertFalse(Domain._meta.managed)

    def test_domain_ordering(self) -> None:
        self.assertEqual(Domain._meta.ordering, ['name'])


class DKIMKeyModelTests(TestCase):
    def test_dkim_meta(self) -> None:
        self.assertEqual(DKIMKey._meta.db_table, 'dkim_keys')
        self.assertFalse(DKIMKey._meta.managed)
