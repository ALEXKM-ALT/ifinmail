"""Tests for mail views."""

from django.test import TestCase


class AutoconfigViewTests(TestCase):
    def test_autoconfig_mozilla(self) -> None:
        response = self.client.get('/mail/config-v1.1.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])

    def test_autoconfig_outlook(self) -> None:
        response = self.client.get('/autodiscover/autodiscover.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])
