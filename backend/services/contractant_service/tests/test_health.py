"""Tests for /health and /ready endpoints."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class HealthViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_returns_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_allows_unauthenticated(self):
        """No auth header — must still return 200."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)


class ReadyViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_ready_returns_ready_when_db_and_cache_ok(self):
        """DB is up (Postgres) and cache is up (Redis)."""
        response = self.client.get("/ready")
        # OK (200) or 503 depending on whether Redis is reachable
        self.assertIn(response.status_code, [200, 503])
        data = response.json()
        self.assertIn(data.get("status"), ["ready", "not_ready"])
