from .base_client import BaseHttpClient


class ContratsClient(BaseHttpClient):

    def get_validations_by_soumission(self, soumission_id: int):
        return self._get(f"/soumissions/{soumission_id}/validations")

    def get_validation(self, validation_id: int):
        return self._get(f"/validations/{validation_id}")
