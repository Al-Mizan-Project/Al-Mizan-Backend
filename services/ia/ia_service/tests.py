from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch


class IaServiceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_detecter_anomalies_creates_records(self):
        payload = {
            "id_appel_offre": 101,
            "soumissions": [
                {
                    "id_soumission": 1,
                    "montant_financier": "100000.00",
                    "signature_document": "abc123",
                },
                {
                    "id_soumission": 2,
                    "montant_financier": "100200.00",
                    "signature_document": "abc123",
                },
            ],
        }
        response = self.client.post("/ia/anomalies/detecter", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertGreaterEqual(response.json().get("anomalies_detectees", 0), 2)

    def test_verifier_conformite_signals_missing_documents(self):
        payload = {
            "required_documents": ["rc", "nif", "attestation_fiscale"],
            "provided_documents": [
                {"type_document": "rc", "is_valid": True},
                {"type_document": "nif", "is_valid": True},
            ],
        }
        response = self.client.post("/ia/conformite/verifier-soumission/500", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("conformite_statut"), "PIECES_MANQUANTES")

    def test_cdc_reviser_detects_bias_terms(self):
        payload = {"texte": "Le fournisseur est obligatoirement une marque imposee."}
        response = self.client.post("/ia/cdc/reviser", payload, format="json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get("needs_human_validation"))
        self.assertGreaterEqual(len(body.get("alerts", [])), 1)

    @patch("ia_service.services.integrations.requests.patch")
    @patch("ia_service.services.integrations.settings.INTERNAL_SERVICE_TOKEN", "ia-internal-token")
    def test_verifier_conformite_triggers_cross_service_patch_calls(self, mock_patch):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status.return_value = None
        mock_patch.return_value = ok_response

        payload = {
            "required_documents": ["rc"],
            "provided_documents": [
                {"id_document": 33, "type_document": "rc", "is_valid": True},
            ],
        }

        response = self.client.post("/ia/conformite/verifier-soumission/501", payload, format="json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["integrations"]["soumission_sync"]["ok"])
        self.assertEqual(len(data["integrations"]["documents_sync"]), 1)
        self.assertTrue(data["integrations"]["documents_sync"][0]["ok"])

        self.assertEqual(mock_patch.call_count, 2)
        soum_call = mock_patch.call_args_list[0]
        doc_call = mock_patch.call_args_list[1]

        self.assertEqual(
            soum_call.args[0],
            f"{settings.SOUMISSIONS_SERVICE_URL}/api/soumissions/501/conformite/",
        )
        self.assertEqual(soum_call.kwargs["json"]["conformite_statut"], "CONFORME")
        self.assertIn("missing_documents", soum_call.kwargs["json"]["conformite_rapport"])
        self.assertEqual(
            soum_call.kwargs["headers"].get("X-Internal-Service-Token"),
            "ia-internal-token",
        )

        self.assertEqual(
            doc_call.args[0],
            f"{settings.DOCUMENTS_SERVICE_URL}/api/documents/33/ia-metadata/",
        )
        self.assertEqual(doc_call.kwargs["json"]["ia_verif_statut"], "VALID")
        self.assertIn("missing_documents", doc_call.kwargs["json"]["ia_verif_details"])

    @patch("ia_service.services.integrations.requests.patch")
    @patch("ia_service.services.integrations.settings.INTERNAL_SERVICE_TOKEN", "ia-internal-token")
    def test_verifier_conformite_partial_document_sync_failure_is_non_blocking(self, mock_patch):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status.return_value = None

        failing_response = MagicMock()
        failing_response.status_code = 500
        failing_response.raise_for_status.side_effect = Exception("document patch failed")

        # Call order:
        # 1) Soumission PATCH -> success
        # 2) Document #10 PATCH -> success
        # 3) Document #11 PATCH -> failure
        mock_patch.side_effect = [ok_response, ok_response, failing_response]

        payload = {
            "required_documents": ["rc", "nif"],
            "provided_documents": [
                {"id_document": 10, "type_document": "rc", "is_valid": True},
                {"id_document": 11, "type_document": "nif", "is_valid": False},
            ],
        }

        response = self.client.post("/ia/conformite/verifier-soumission/902", payload, format="json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["conformite_statut"], "NON_CONFORME")
        self.assertTrue(data["integrations"]["soumission_sync"]["ok"])
        self.assertEqual(len(data["integrations"]["documents_sync"]), 2)
        self.assertTrue(data["integrations"]["documents_sync"][0]["ok"])
        self.assertFalse(data["integrations"]["documents_sync"][1]["ok"])