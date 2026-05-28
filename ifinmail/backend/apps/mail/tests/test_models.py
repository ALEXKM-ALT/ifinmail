"""Tests for mail models."""
from django.test import TestCase

from backend.apps.domains.models import Domain

from ..models import Alias, Mailbox


class MailboxModelTests(TestCase):
    def test_mailbox_str(self) -> None:
        domain = Domain(name="example.com")
        mailbox = Mailbox(domain=domain, local_part="user")
        self.assertEqual(str(mailbox), "user@example.com")


class AliasModelTests(TestCase):
    def test_alias_str(self) -> None:
        domain = Domain(name="example.com")
        alias = Alias(domain=domain, source="src", destination="dst")
        self.assertEqual(str(alias), "src → dst")
