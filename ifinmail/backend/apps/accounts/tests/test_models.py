"""Tests for accounts models."""
from django.db import connection
from django.test import TransactionTestCase
from unittest.mock import patch

from ..models import MailUser


def create_unmanaged_table(model: type) -> None:
    with patch.object(model._meta, "managed", True), \
         connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.create_model(model)


def drop_unmanaged_table(model: type) -> None:
    with patch.object(model._meta, "managed", True), \
         connection.schema_editor(atomic=False) as schema_editor:
        schema_editor.delete_model(model)


class MailUserModelTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(MailUser)

    @classmethod
    def tearDownClass(cls) -> None:
        drop_unmanaged_table(MailUser)
        super().tearDownClass()

    def test_create_user(self) -> None:
        user = MailUser.objects.create_user(email="test@ifinmail.test", password="pass")
        self.assertEqual(user.email, "test@ifinmail.test")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self) -> None:
        user = MailUser.objects.create_superuser(email="super@ifinmail.test", password="pass")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_str(self) -> None:
        user = MailUser(email="test@example.com")
        self.assertEqual(str(user), "test@example.com")

    def test_has_perm_superuser(self) -> None:
        user = MailUser(is_superuser=True)
        self.assertTrue(user.has_perm("any.permission"))

    def test_has_perm_non_superuser(self) -> None:
        user = MailUser(is_superuser=False)
        self.assertFalse(user.has_perm("any.permission"))

    def test_has_module_perms(self) -> None:
        user = MailUser(is_superuser=True)
        self.assertTrue(user.has_module_perms("any_app"))

    def test_create_user_no_email_raises(self) -> None:
        with self.assertRaises(ValueError):
            MailUser.objects.create_user(email="", password="pass")
