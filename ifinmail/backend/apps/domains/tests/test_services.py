"""Tests for domains services."""

from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase

from backend.apps.domains.models import DKIMKey, Domain
from backend.apps.domains.services import DomainService
from backend.apps.mail.models import Alias, Mailbox


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


class DomainServiceTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(Domain)
        create_unmanaged_table(DKIMKey)
        create_unmanaged_table(Mailbox)
        create_unmanaged_table(Alias)

    @classmethod
    def tearDownClass(cls) -> None:
        import contextlib

        for tbl in (Alias, Mailbox, DKIMKey, Domain):
            with contextlib.suppress(Exception):
                drop_unmanaged_table(tbl)
        super().tearDownClass()

    def _fixture_teardown(self=None) -> None:
        pass

    def _fixture_setup(self=None) -> None:
        pass

    def tearDown(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM domains')
        super().tearDown()

    def test_get_domain_stats_empty(self) -> None:
        stats = DomainService.get_domain_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats['total'], 0)

    def test_get_domain_count(self) -> None:
        self.assertEqual(DomainService.get_domain_count(), 0)

    def test_get_or_create_domain(self) -> None:
        domain, created = DomainService.get_or_create_domain(name='test.example')
        self.assertTrue(created)
        self.assertEqual(domain.name, 'test.example')

    def test_get_or_create_domain_existing(self) -> None:
        Domain.objects.create(name='existing.example')
        domain, created = DomainService.get_or_create_domain(name='existing.example')
        self.assertFalse(created)
        self.assertEqual(domain.name, 'existing.example')

    def test_get_domain_by_name(self) -> None:
        Domain.objects.create(name='find.example')
        domain = DomainService.get_domain_by_name('find.example')
        self.assertIsNotNone(domain)
        self.assertEqual(domain.name, 'find.example')

    def test_get_domain_by_name_missing(self) -> None:
        self.assertIsNone(DomainService.get_domain_by_name('missing.example'))

    def test_create_domain(self) -> None:
        domain = DomainService.create_domain(name='new.example')
        self.assertEqual(domain.name, 'new.example')

    def test_create_domain_validates_length(self) -> None:
        with self.assertRaises(ValueError):
            DomainService.create_domain(name='x' * 300)

    def test_delete_domain(self) -> None:
        Domain.objects.create(name='delete.example')
        result = DomainService.delete_domain('delete.example')
        self.assertTrue(result)
        self.assertIsNone(DomainService.get_domain_by_name('delete.example'))

    def test_delete_domain_missing(self) -> None:
        result = DomainService.delete_domain('notexist.example')
        self.assertFalse(result)

    def test_get_domains_paginated(self) -> None:
        for i in range(30):
            Domain.objects.create(name=f'domain-{i:04d}.example')
        page1, has_next = DomainService.get_domains_paginated(1, 25)
        self.assertEqual(len(page1), 25)
        self.assertTrue(has_next)
        page2, has_next2 = DomainService.get_domains_paginated(2, 25)
        self.assertEqual(len(page2), 5)
        self.assertFalse(has_next2)

    def test_get_domain_verification_rows(self) -> None:
        Domain.objects.create(name='v.example', verified=True, mx_verified=True)
        Domain.objects.create(name='nv.example')
        rows = DomainService.get_domain_verification_rows(['v.example', 'nv.example'])
        self.assertEqual(len(rows), 2)

    def test_get_all_domains(self) -> None:
        Domain.objects.create(name='z.example')
        Domain.objects.create(name='a.example')
        domains = DomainService.get_all_domains()
        self.assertEqual(list(domains.values_list('name', flat=True)), ['a.example', 'z.example'])

    def test_get_domain_stats_with_data(self) -> None:
        Domain.objects.create(name='one.example', verified=True, mx_verified=True)
        Domain.objects.create(name='two.example')
        stats = DomainService.get_domain_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['verified'], 1)
