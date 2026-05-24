from .base_client import BaseHttpClient


class SoumissionsClient(BaseHttpClient):

    def get_soumission(self, soumission_id: int):
        return self._get(f"/soumissions/{soumission_id}")

    def get_operateur_soumissions(self, operateur_id: int):
        return self._get(f"/operateurs-economiques/{operateur_id}/soumissions")

    def get_soumissionnaires_by_appel(self, appel_id: int):
        return self._get(f"/appels-offres/{appel_id}/soumissions")