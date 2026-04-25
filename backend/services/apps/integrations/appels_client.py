from .base_client import BaseHttpClient


class AppelsClient(BaseHttpClient):

    def get_appel_offre(self, appel_id: int):
        return self._get(f"/appels-offres/{appel_id}")

    def get_service_appels(self, service_id: int):
        return self._get(f"/services-contractants/{service_id}/appels-offres")
