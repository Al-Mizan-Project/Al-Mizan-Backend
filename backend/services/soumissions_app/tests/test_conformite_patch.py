from django.test import override_settings
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from soumissions_app.models import Soumission, SoumissionStatut


class SoumissionConformitePatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="ia_service", password="test-pass-123")
        self.client.force_authenticate(user=user)
        self.soumission = Soumission.objects.create(
            id_appel_offre=42,
            id_soumissionnaire=7,
            offre_financiere_chiffree_url="http://minio/offer.enc",
            cle_dechiffrement_hash="encrypted-key",
            statut=SoumissionStatut.SOUMIS,
        )

    def test_patch_conformite_success(self):
        url = f"/api/soumissions/{self.soumission.id_soumission}/conformite/"
        payload = {
            "conformite_statut": "CONFORME",
            "conformite_rapport": {"missing_documents": []},
        }
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.soumission.refresh_from_db()
        self.assertEqual(self.soumission.conformite_statut, "CONFORME")
        self.assertIn("missing_documents", self.soumission.conformite_rapport)

    def test_patch_conformite_requires_status(self):
        url = f"/api/soumissions/{self.soumission.id_soumission}/conformite/"
        response = self.client.patch(url, {"conformite_rapport": "x"}, format="json")
        self.assertEqual(response.status_code, 400)

    @override_settings(INTERNAL_SERVICE_TOKEN="ia-internal-token")
    def test_patch_conformite_allows_internal_token_without_user_auth(self):
        client = APIClient()
        url = f"/api/soumissions/{self.soumission.id_soumission}/conformite/"
        payload = {
            "conformite_statut": "CONFORME",
            "conformite_rapport": {"source": "ia"},
        }

        response = client.patch(
            url,
            payload,
            format="json",
            HTTP_X_INTERNAL_SERVICE_TOKEN="ia-internal-token",
        )

        self.assertEqual(response.status_code, 200)
        self.soumission.refresh_from_db()
        self.assertEqual(self.soumission.conformite_statut, "CONFORME")

    @override_settings(INTERNAL_SERVICE_TOKEN="ia-internal-token")
    def test_patch_conformite_rejects_missing_internal_token_without_user_auth(self):
        client = APIClient()
        url = f"/api/soumissions/{self.soumission.id_soumission}/conformite/"
        payload = {
            "conformite_statut": "CONFORME",
            "conformite_rapport": {"source": "ia"},
        }

        response = client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, 401)