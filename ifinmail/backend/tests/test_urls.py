"""URL routing tests."""
from django.test import TestCase
from django.urls import reverse


class URLRoutingTests(TestCase):
    def test_health_check(self):
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)

    def test_health_check_returns_json(self):
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response["Content-Type"], "application/json")

    def test_accounts_root_redirects(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
