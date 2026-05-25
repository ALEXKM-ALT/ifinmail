"""Tests for accounts app views and services."""
from django.test import TestCase
from django.urls import reverse

from .models import MailUser


class DashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = MailUser.objects.create_user(
            email="admin@ifinmail.test",
            password="testpass123",
            is_staff=True,
        )

    def test_dashboard_redirects_when_unauthenticated(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible_when_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 200)


class LoginViewTests(TestCase):
    def test_login_page_loads(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        user = MailUser.objects.create_user(
            email="admin@ifinmail.test",
            password="testpass123",
            is_staff=True,
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "admin@ifinmail.test", "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "admin@ifinmail.test", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password")

    def test_logout(self):
        user = MailUser.objects.create_user(
            email="admin@ifinmail.test",
            password="testpass123",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))


class MailUserModelTests(TestCase):
    def test_create_user(self):
        user = MailUser.objects.create_user(email="test@ifinmail.test", password="pass")
        self.assertEqual(user.email, "test@ifinmail.test")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        user = MailUser.objects.create_superuser(email="super@ifinmail.test", password="pass")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
