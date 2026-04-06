from django.test import TestCase
from django.urls import reverse


class HealthViewTest(TestCase):
    def test_health_returns_200(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_returns_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.json(), {"status": "ok"})


class ReadyViewTest(TestCase):
    def test_ready_returns_200_or_503(self):
        response = self.client.get("/ready")
        self.assertIn(response.status_code, [200, 503])

    def test_ready_has_status_field(self):
        response = self.client.get("/ready")
        data = response.json()
        self.assertIn("status", data)


class OpenAPIViewTest(TestCase):
    def test_openapi_json_returns_200(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)

    def test_openapi_json_has_paths(self):
        import json
        response = self.client.get("/openapi.json?format=json")
        data = json.loads(response.content)
        self.assertIn("paths", data)
