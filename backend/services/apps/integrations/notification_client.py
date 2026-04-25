from .base_client import BaseHttpClient


class NotificationClient(BaseHttpClient):

    def send_notification(self, payload: dict):
        return self._post("/notifications", payload)

    def send_bulk_notifications(self, payload: dict):
        return self._post("/notifications/envoi-masse", payload)
