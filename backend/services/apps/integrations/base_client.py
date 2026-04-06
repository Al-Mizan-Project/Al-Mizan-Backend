from django.conf import settings
import requests


class BaseHttpClient:

    def __init__(self, base_url: str, timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        response = requests.get(url, timeout=self.timeout, headers=self._headers())
        return self._handle_response(response)

    def _post(self, path: str, data: dict):
        url = f"{self.base_url}{path}"
        response = requests.post(url, json=data, timeout=self.timeout, headers=self._headers())
        return self._handle_response(response)

    def _patch(self, path: str, data: dict):
        url = f"{self.base_url}{path}"
        response = requests.patch(url, json=data, timeout=self.timeout, headers=self._headers())
        return self._handle_response(response)

    def _headers(self):
        token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
        if not token:
            return {}
        return {"X-Internal-Service-Token": token}

    def _handle_response(self, response: requests.Response):
        if response.status_code >= 200 and response.status_code < 300:
            if response.content:
                return response.json()
            return None

        raise Exception(
            f"HTTP Error {response.status_code}: {response.text}"
        )
