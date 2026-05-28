"""Tests for accounts views."""
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
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


class DashboardViewTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(MailUser)

    @classmethod
    def tearDownClass(cls) -> None:
        drop_unmanaged_table(MailUser)
        super().tearDownClass()

    def _fixture_teardown(self) -> None:
        pass

    def _fixture_setup(self) -> None:
        pass

    def tearDown(self) -> None:
        MailUser.objects.all().delete()
        super().tearDown()

    def setUp(self) -> None:
        super().setUp()
        self.user = MailUser.objects.create_user(
            email="admin@ifinmail.test",
            password="testpass123",
            is_staff=True,
        )

    def test_dashboard_redirects_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible_when_authenticated(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_admin_pages_redirect_when_unauthenticated(self) -> None:
        for route in [
            "accounts:logs",
            "accounts:spam_filtering",
            "accounts:user_management",
            "accounts:branding_identity",
        ]:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 302)

    def test_admin_pages_render_for_staff(self) -> None:
        self.client.force_login(self.user)
        cases = [
            ("accounts:logs", "System Logs"),
            ("accounts:spam_filtering", "Spam Filtering"),
            ("accounts:user_management", "User Management"),
            ("accounts:branding_identity", "Branding & Identity"),
        ]
        for route, title in cases:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, title)


class LoginViewTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_unmanaged_table(MailUser)

    @classmethod
    def tearDownClass(cls) -> None:
        drop_unmanaged_table(MailUser)
        super().tearDownClass()

    def _fixture_teardown(self) -> None:
        pass

    def _fixture_setup(self) -> None:
        pass

    def tearDown(self) -> None:
        MailUser.objects.all().delete()
        super().tearDown()

    def test_login_page_loads(self) -> None:
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)

    def test_login_success(self) -> None:
        MailUser.objects.create_user(
            email="admin@ifinmail.test",
            password="testpass123",
            is_staff=True,
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "admin@ifinmail.test", "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_login_invalid_credentials(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "admin@ifinmail.test", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password")

    def test_logout(self) -> None:
        user = MailUser.objects.create_user(
            email="admin@ifinmail.test",
            password="testpass123",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
