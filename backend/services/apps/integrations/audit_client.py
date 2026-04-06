from .base_client import BaseHttpClient


class AuditClient(BaseHttpClient):

    def log_action(self, payload: dict):
        return self._post("/journaux-audit/create/", payload)

    def get_entity_logs(self, entity_type: str, entity_id: int):
        return self._get(f"/journaux-audit/entity/{entity_type}/{entity_id}/")
