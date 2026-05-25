"""Tests for mail app views."""
from django.test import TestCase
from django.urls import reverse

from backend.apps.accounts.models import MailUser


class InboxViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = MailUser.objects.create_user(
            email="user@ifinmail.test",
            password="testpass123",
        )

    def test_inbox_redirects_when_unauthenticated(self):
        response = self.client.get(reverse("mail:inbox"))
        self.assertEqual(response.status_code, 302)

    def test_inbox_accessible_when_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("mail:inbox"))
        self.assertEqual(response.status_code, 200)
