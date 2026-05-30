"""Tests for accounts services."""

from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase

from ..models import MailUser
from ..services import UserService


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


class UserServiceTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(MailUser)

    @classmethod
    def tearDownClass(cls) -> None:
        drop_unmanaged_table(MailUser)
        super().tearDownClass()

    def _fixture_teardown(self=None) -> None:
        pass

    def _fixture_setup(self=None) -> None:
        pass

    def tearDown(self) -> None:
        MailUser.objects.all().delete()
        super().tearDown()

    def test_get_active_count(self) -> None:
        MailUser.objects.create_user(email='a@test.test', password='p', is_active=True)
        MailUser.objects.create_user(email='b@test.test', password='p', is_active=False)
        self.assertEqual(UserService.get_active_count(), 1)

    def test_has_staff_users_false_when_none(self) -> None:
        self.assertFalse(UserService.has_staff_users())

    def test_has_staff_users_true_when_exists(self) -> None:
        MailUser.objects.create_user(email='admin@test.test', password='p', is_staff=True)
        self.assertTrue(UserService.has_staff_users())

    def test_get_user_by_email_found(self) -> None:
        MailUser.objects.create_user(email='find@test.test', password='p')
        user = UserService.get_user_by_email('find@test.test')
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'find@test.test')

    def test_get_user_by_email_not_found(self) -> None:
        self.assertIsNone(UserService.get_user_by_email('nobody@test.test'))

    def test_create_user_with_staff(self) -> None:
        user = UserService.create_user(email='staff@test.test', password='p', is_staff=True)
        self.assertTrue(user.is_staff)

    def test_create_user_validates_email_length(self) -> None:
        with self.assertRaises(ValueError):
            UserService.create_user(email='x' * 300, password='p')

    def test_get_all_users_ordered(self) -> None:
        MailUser.objects.create_user(email='b@test.test', password='p')
        MailUser.objects.create_user(email='a@test.test', password='p')
        users = UserService.get_all_users()
        self.assertEqual(
            list(users.values_list('email', flat=True)), ['a@test.test', 'b@test.test']
        )
