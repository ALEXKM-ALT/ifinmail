"""Tests for mail services."""
from django.db import connection
from django.test import TransactionTestCase
from unittest.mock import patch

from backend.apps.domains.models import Domain

from ..models import Alias, Mailbox
from ..services import MailService


def create_unmanaged_table(model: type) -> None:
    with patch.object(model._meta, "managed", True), \
         connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.create_model(model)


def drop_unmanaged_table(model: type) -> None:
    with patch.object(model._meta, "managed", True), \
         connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.delete_model(model)


class MailServiceTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(Mailbox)
        create_unmanaged_table(Alias)
        create_unmanaged_table(Domain)

    @classmethod
    def tearDownClass(cls) -> None:
        for tbl in (Alias, Mailbox, Domain):
            try:
                drop_unmanaged_table(tbl)
            except Exception:
                pass
        super().tearDownClass()

    def _fixture_teardown(self) -> None:
        pass

    def _fixture_setup(self) -> None:
        pass

    def tearDown(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM aliases")
            cursor.execute("DELETE FROM mailboxes")
            cursor.execute("DELETE FROM domains")
        super().tearDown()

    def test_get_mailbox_count(self) -> None:
        domain = Domain.objects.create(name="count.example")
        Mailbox.objects.create(domain=domain, local_part="user1")
        Mailbox.objects.create(domain=domain, local_part="user2")
        self.assertEqual(MailService.get_mailbox_count(), 2)

    def test_get_or_create_mailbox(self) -> None:
        domain = Domain.objects.create(name="mb.example")
        mb, created = MailService.get_or_create_mailbox(domain=domain, local_part="test")
        self.assertTrue(created)
        self.assertEqual(mb.local_part, "test")
        mb2, created2 = MailService.get_or_create_mailbox(domain=domain, local_part="test")
        self.assertFalse(created2)

    def test_create_mailbox(self) -> None:
        domain = Domain.objects.create(name="create.example")
        mb = MailService.create_mailbox(domain=domain, local_part="newuser")
        self.assertEqual(mb.local_part, "newuser")
        self.assertEqual(mb.quota_bytes, 0)
