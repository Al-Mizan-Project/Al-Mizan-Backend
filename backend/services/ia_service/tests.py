from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from ia_service.models import DetectionAnomalieIA
from ia_service.services.anomalies import (
    detect_price_and_similarity_anomalies,
    generate_anomaly_summary,
)
from ia_service.services.ocr import extract_document_text, extract_documents_text_parallel
from ia_service.services.saucissonnage import detect_saucissonnage


# ===========================================================================
# Unit Tests — Anomaly Detection Algorithms
# ===========================================================================
class AnomalyDetectionAlgorithmsTests(TestCase):
    """Test individual anomaly detection algorithms."""

    def test_document_similarity_detected(self):
        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000", "signature_document": "abc123"},
            {"id_soumission": 2, "montant_financier": "200000", "signature_document": "abc123"},
            {"id_soumission": 3, "montant_financier": "150000", "signature_document": "xyz789"},
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        doc_sim = [a for a in anomalies if a["type_anomalie"] == "SIMILARITE_DOCUMENTAIRE"]
        self.assertGreaterEqual(len(doc_sim), 2)
        # Both soumissions 1 and 2 should be flagged
        flagged_ids = {a["id_soumission"] for a in doc_sim}
        self.assertIn(1, flagged_ids)
        self.assertIn(2, flagged_ids)

    def test_price_similarity_detected(self):
        """Offers too close to the mean should be flagged."""
        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000.00"},
            {"id_soumission": 2, "montant_financier": "100200.00"},
            {"id_soumission": 3, "montant_financier": "100100.00"},
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        price_sim = [a for a in anomalies if a["type_anomalie"] == "SIMILARITE_PRIX"]
        self.assertGreaterEqual(len(price_sim), 1)

    def test_pairwise_proximity_detected(self):
        """Two offers extremely close in price should trigger bilateral collusion alert."""
        soumissions = [
            {"id_soumission": 1, "montant_financier": "500000.00"},
            {"id_soumission": 2, "montant_financier": "500100.00"},
            {"id_soumission": 3, "montant_financier": "800000.00"},
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        cluster = [a for a in anomalies if a["type_anomalie"] == "COLLUSION_CLUSTER_PRIX"]
        self.assertGreaterEqual(len(cluster), 1)

    def test_low_dispersion_detected(self):
        """Very low CV across all offers should be flagged."""
        # All offers within 1% of each other
        soumissions = [
            {"id_soumission": 1, "montant_financier": "1000000.00"},
            {"id_soumission": 2, "montant_financier": "1001000.00"},
            {"id_soumission": 3, "montant_financier": "1000500.00"},
            {"id_soumission": 4, "montant_financier": "1000200.00"},
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        dispersion = [a for a in anomalies if a["type_anomalie"] == "DISPERSION_ANORMALE"]
        self.assertGreaterEqual(len(dispersion), 1)

    def test_abnormally_low_price_detected(self):
        """Statistical outlier (low) should be flagged."""
        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000.00"},
            {"id_soumission": 2, "montant_financier": "110000.00"},
            {"id_soumission": 3, "montant_financier": "105000.00"},
            {"id_soumission": 4, "montant_financier": "10000.00"},  # Outlier
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        low = [a for a in anomalies if a["type_anomalie"] == "PRIX_ANORMALEMENT_BAS"]
        self.assertGreaterEqual(len(low), 1)
        self.assertEqual(low[0]["id_soumission"], 4)

    def test_abnormally_high_price_detected(self):
        """Statistical outlier (high) should be flagged as cover bid."""
        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000.00"},
            {"id_soumission": 2, "montant_financier": "110000.00"},
            {"id_soumission": 3, "montant_financier": "105000.00"},
            {"id_soumission": 4, "montant_financier": "500000.00"},  # Outlier
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        high = [a for a in anomalies if a["type_anomalie"] == "PRIX_ANORMALEMENT_ELEVE"]
        self.assertGreaterEqual(len(high), 1)
        self.assertEqual(high[0]["id_soumission"], 4)

    def test_complementary_bids_detected(self):
        """Cover bid pattern: one low offer + many clustered high offers."""
        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000.00"},  # Target winner
            {"id_soumission": 2, "montant_financier": "200000.00"},  # Cover
            {"id_soumission": 3, "montant_financier": "200500.00"},  # Cover
            {"id_soumission": 4, "montant_financier": "201000.00"},  # Cover
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        comp = [a for a in anomalies if a["type_anomalie"] == "OFFRES_COMPLEMENTAIRES"]
        self.assertGreaterEqual(len(comp), 1)

    def test_no_anomalies_for_normal_competition(self):
        """Well-spread prices should not trigger collusion alerts."""
        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000.00"},
            {"id_soumission": 2, "montant_financier": "130000.00"},
            {"id_soumission": 3, "montant_financier": "160000.00"},
        ]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        # Should have no or very few anomalies for healthy competition
        collusion_types = {"SIMILARITE_PRIX", "COLLUSION_CLUSTER_PRIX", "DISPERSION_ANORMALE"}
        collusion = [a for a in anomalies if a["type_anomalie"] in collusion_types]
        self.assertEqual(len(collusion), 0)

    def test_empty_soumissions_returns_empty(self):
        anomalies = detect_price_and_similarity_anomalies([])
        self.assertEqual(anomalies, [])

    def test_single_soumission_no_crash(self):
        soumissions = [{"id_soumission": 1, "montant_financier": "100000"}]
        anomalies = detect_price_and_similarity_anomalies(soumissions)
        self.assertIsInstance(anomalies, list)

    def test_anomaly_summary_generation(self):
        anomalies = [
            {
                "id_soumission": 1,
                "type_anomalie": "SIMILARITE_PRIX",
                "niveau_severite": "ELEVEE",
                "score_confiance": Decimal("0.85"),
                "details": "test",
            },
            {
                "id_soumission": 2,
                "type_anomalie": "PRIX_ANORMALEMENT_BAS",
                "niveau_severite": "MOYEN",
                "score_confiance": Decimal("0.80"),
                "details": "test",
            },
        ]
        summary = generate_anomaly_summary(anomalies, 5)
        self.assertEqual(summary["total_anomalies"], 2)
        self.assertEqual(summary["soumissions_affectees"], 2)
        self.assertIn("niveau_risque", summary)
        self.assertIn("recommandation", summary)


class OcrServiceTests(TestCase):
    def test_extract_document_text_empty_payload(self):
        result = extract_document_text(payload=b"", filename="file.pdf")
        self.assertEqual(result["engine"], "none")
        self.assertEqual(result["text"], "")
        self.assertFalse(result["used"])

    @patch("ia_service.services.ocr._extract_pdf_text", return_value="texte pdf")
    def test_extract_document_text_pdf_uses_pypdf(self, mock_pdf):
        result = extract_document_text(payload=b"dummy", filename="piece.pdf")
        self.assertEqual(result["engine"], "pypdf")
        self.assertEqual(result["text"], "texte pdf")
        self.assertTrue(result["used"])
        mock_pdf.assert_called_once()

    @patch("ia_service.services.ocr._extract_image_ocr_text", return_value="texte image")
    def test_extract_document_text_image_uses_tesseract(self, mock_img):
        result = extract_document_text(payload=b"dummy", filename="piece.png")
        self.assertEqual(result["engine"], "tesseract")
        self.assertEqual(result["text"], "texte image")
        self.assertTrue(result["used"])
        mock_img.assert_called_once()

    @patch("ia_service.services.ocr._extract_image_ocr_text", return_value="fallback texte")
    def test_extract_document_text_fallback_unknown_extension(self, mock_img):
        with self.settings(OCR_FALLBACK_IMAGE_ATTEMPT=True):
            result = extract_document_text(payload=b"dummy", filename="piece.bin")
        self.assertEqual(result["engine"], "tesseract")
        self.assertEqual(result["text"], "fallback texte")
        self.assertTrue(result["used"])
        mock_img.assert_called_once()

    @patch("ia_service.services.ocr._extract_pdf_text", return_value="")
    @patch("ia_service.services.ocr._extract_pdf_ocr_text", return_value="registre de commerce")
    def test_pdf_ocr_fallback_for_scanned_pdf(self, mock_pdf_ocr, mock_pdf_text):
        """When pypdf returns empty text, pdf2image+tesseract should be tried."""
        result = extract_document_text(payload=b"scanned-pdf-bytes", filename="scan.pdf")
        self.assertEqual(result["engine"], "pdf2image+tesseract")
        self.assertEqual(result["text"], "registre de commerce")
        self.assertTrue(result["used"])
        mock_pdf_text.assert_called_once()
        mock_pdf_ocr.assert_called_once()

    def test_file_size_limit_rejects_large_files(self):
        """Files exceeding MAX_OCR_FILE_SIZE should be skipped."""
        large_payload = b"x" * (1024 * 1024 + 1)  # ~1 MB
        with self.settings(MAX_OCR_FILE_SIZE=1024 * 1024):  # 1 MB limit
            result = extract_document_text(payload=large_payload, filename="big.pdf")
        self.assertFalse(result["used"])
        self.assertEqual(result["engine"], "none")
        self.assertEqual(result.get("skipped_reason"), "file_too_large")

    @patch("ia_service.services.ocr._extract_pdf_text", return_value="small file text")
    def test_file_size_limit_allows_small_files(self, mock_pdf):
        """Files under MAX_OCR_FILE_SIZE should be processed normally."""
        small_payload = b"x" * 100
        with self.settings(MAX_OCR_FILE_SIZE=1024 * 1024):
            result = extract_document_text(payload=small_payload, filename="small.pdf")
        self.assertTrue(result["used"])
        self.assertEqual(result["engine"], "pypdf")

    @patch("ia_service.services.ocr._extract_pdf_text")
    def test_parallel_extraction_preserves_order(self, mock_pdf):
        """extract_documents_text_parallel must return results in input order."""
        mock_pdf.side_effect = ["texte A", "texte B", "texte C"]
        items = [
            (b"a", "a.pdf"),
            (b"b", "b.pdf"),
            (b"c", "c.pdf"),
        ]
        results = extract_documents_text_parallel(items)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["text"], "texte A")
        self.assertEqual(results[1]["text"], "texte B")
        self.assertEqual(results[2]["text"], "texte C")

    @patch("ia_service.services.ocr._extract_image_ocr_text", return_value="single")
    def test_parallel_single_item_uses_sequential(self, mock_img):
        """A single item should not spin up a thread pool."""
        results = extract_documents_text_parallel([(b"x", "img.png")])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "single")


# ===========================================================================
# Unit Tests — Saucissonnage Detection
# ===========================================================================
class SaucissonnageDetectionTests(TestCase):
    """Test saucissonnage (market splitting) detection algorithms."""

    def test_cumulative_threshold_breach_detected(self):
        """Multiple small contracts exceeding threshold when combined."""
        appels = [
            {
                "id_appel_offre": 1,
                "id_service_contractant": 10,
                "titre": "Acquisition equipement informatique lot 1",
                "description": "Achat ordinateurs bureau",
                "montant_estime": "5000000",
                "date_publication": "2025-01-15",
                "type_procedure": "consultation",
            },
            {
                "id_appel_offre": 2,
                "id_service_contractant": 10,
                "titre": "Acquisition equipement informatique lot 2",
                "description": "Achat ordinateurs portables",
                "montant_estime": "5500000",
                "date_publication": "2025-02-01",
                "type_procedure": "consultation",
            },
            {
                "id_appel_offre": 3,
                "id_service_contractant": 10,
                "titre": "Acquisition equipement informatique lot 3",
                "description": "Achat serveurs informatiques",
                "montant_estime": "4000000",
                "date_publication": "2025-02-15",
                "type_procedure": "consultation",
            },
        ]
        result = detect_saucissonnage(appels)
        anomalies = result["anomalies"]
        cumul = [a for a in anomalies if a["type_anomalie"] == "SAUCISSONNAGE_CUMUL_SEUIL"]
        # 5M + 5.5M + 4M = 14.5M > 12M threshold
        self.assertGreaterEqual(len(cumul), 1)

    def test_threshold_proximity_detected(self):
        """Contract amount suspiciously close to a threshold."""
        appels = [
            {
                "id_appel_offre": 1,
                "id_service_contractant": 10,
                "titre": "Travaux de renovation",
                "montant_estime": "11500000",  # 95.8% of 12M threshold
                "date_publication": "2025-03-01",
                "type_procedure": "consultation",
            },
        ]
        result = detect_saucissonnage(appels)
        anomalies = result["anomalies"]
        proximity = [a for a in anomalies if a["type_anomalie"] == "SAUCISSONNAGE_PROXIMITE_SEUIL"]
        self.assertGreaterEqual(len(proximity), 1)

    def test_temporal_clustering_detected(self):
        """Similar contracts from same entity in short timeframe."""
        appels = [
            {
                "id_appel_offre": i,
                "id_service_contractant": 10,
                "titre": f"Fourniture papier bureau lot {i}",
                "description": "Achat papier imprimante",
                "montant_estime": "3000000",
                "date_publication": f"2025-01-{10+i:02d}",
                "type_procedure": "gre_a_gre",
            }
            for i in range(1, 5)
        ]
        result = detect_saucissonnage(appels)
        anomalies = result["anomalies"]
        temporal = [a for a in anomalies if a["type_anomalie"] == "SAUCISSONNAGE_TEMPOREL"]
        self.assertGreaterEqual(len(temporal), 1)

    def test_no_saucissonnage_for_different_subjects(self):
        """Contracts with different subjects should not be flagged."""
        appels = [
            {
                "id_appel_offre": 1,
                "id_service_contractant": 10,
                "titre": "Construction batiment",
                "montant_estime": "5000000",
                "date_publication": "2025-01-15",
                "type_procedure": "consultation",
            },
            {
                "id_appel_offre": 2,
                "id_service_contractant": 10,
                "titre": "Fourniture vehicules transport",
                "montant_estime": "6000000",
                "date_publication": "2025-02-01",
                "type_procedure": "consultation",
            },
        ]
        result = detect_saucissonnage(appels)
        anomalies = result["anomalies"]
        cumul = [a for a in anomalies if a["type_anomalie"] == "SAUCISSONNAGE_CUMUL_SEUIL"]
        self.assertEqual(len(cumul), 0)

    def test_saucissonnage_summary_includes_risk_score(self):
        appels = [
            {
                "id_appel_offre": 1,
                "id_service_contractant": 10,
                "titre": "Achat materiel informatique 1",
                "montant_estime": "11000000",
                "date_publication": "2025-01-01",
                "type_procedure": "consultation",
            },
        ]
        result = detect_saucissonnage(appels)
        summary = result["summary"]
        self.assertIn("score_risque_saucissonnage", summary)
        self.assertIn("niveau_risque", summary)
        self.assertIn("recommandation", summary)

    def test_empty_appels_returns_clean_result(self):
        result = detect_saucissonnage([])
        self.assertEqual(result["anomalies"], [])
        self.assertEqual(result["summary"]["total_anomalies"], 0)
        self.assertEqual(result["summary"]["niveau_risque"], "AUCUN")


# ===========================================================================
# API Tests — Endpoints
# ===========================================================================
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
        data = response.json()
        self.assertGreaterEqual(data.get("anomalies_detectees", 0), 2)
        self.assertIn("summary", data)
        self.assertIn("items", data)

    def test_detecter_anomalies_returns_summary(self):
        payload = {
            "id_appel_offre": 102,
            "soumissions": [
                {"id_soumission": 1, "montant_financier": "100000"},
                {"id_soumission": 2, "montant_financier": "100050"},
                {"id_soumission": 3, "montant_financier": "100025"},
            ],
        }
        response = self.client.post("/ia/anomalies/detecter", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        summary = data.get("summary", {})
        self.assertIn("score_risque_global", summary)
        self.assertIn("niveau_risque", summary)
        self.assertIn("recommandation", summary)

    def test_detecter_saucissonnage_endpoint(self):
        payload = {
            "appels": [
                {
                    "id_appel_offre": 1,
                    "id_service_contractant": 10,
                    "titre": "Achat equipement info lot 1",
                    "description": "Achat ordinateurs",
                    "montant_estime": "5000000",
                    "date_publication": "2025-01-10",
                    "type_procedure": "consultation",
                },
                {
                    "id_appel_offre": 2,
                    "id_service_contractant": 10,
                    "titre": "Achat equipement info lot 2",
                    "description": "Achat imprimantes",
                    "montant_estime": "5500000",
                    "date_publication": "2025-01-20",
                    "type_procedure": "consultation",
                },
                {
                    "id_appel_offre": 3,
                    "id_service_contractant": 10,
                    "titre": "Achat equipement info lot 3",
                    "description": "Achat serveurs",
                    "montant_estime": "4000000",
                    "date_publication": "2025-02-01",
                    "type_procedure": "consultation",
                },
            ],
        }
        response = self.client.post("/ia/saucissonnage/detecter", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("items", data)

    def test_anomalies_list_filters_by_category(self):
        # Create collusion anomaly
        DetectionAnomalieIA.objects.create(
            id_appel_offre=1, id_soumission=1,
            type_anomalie="SIMILARITE_PRIX",
            niveau_severite="ELEVEE", score_confiance=Decimal("0.85"),
            details="test", statut_examen="A_REVOIR",
        )
        # Create saucissonnage anomaly
        DetectionAnomalieIA.objects.create(
            id_appel_offre=1,
            type_anomalie="SAUCISSONNAGE_CUMUL_SEUIL",
            niveau_severite="CRITIQUE", score_confiance=Decimal("0.95"),
            details="test", statut_examen="A_REVOIR",
        )

        # Filter collusion only
        response = self.client.get("/ia/anomalies?categorie=collusion")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for item in data:
            self.assertFalse(item["type_anomalie"].startswith("SAUCISSONNAGE"))

        # Filter saucissonnage only
        response = self.client.get("/ia/anomalies?categorie=saucissonnage")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for item in data:
            self.assertTrue(item["type_anomalie"].startswith("SAUCISSONNAGE"))

    def test_anomalie_statut_examen_patch_with_comment(self):
        record = DetectionAnomalieIA.objects.create(
            id_appel_offre=1, id_soumission=1,
            type_anomalie="SIMILARITE_PRIX",
            niveau_severite="ELEVEE", score_confiance=Decimal("0.85"),
            details="test", statut_examen="A_REVOIR",
        )
        payload = {
            "statut_examen": "CONFIRMEE",
            "commentaire_examen": "Anomalie confirmée après vérification manuelle.",
        }
        response = self.client.patch(
            f"/ia/anomalies/{record.id_detection_anomalie_ia}/statut-examen",
            payload, format="json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["statut_examen"], "CONFIRMEE")
        self.assertEqual(data["commentaire_examen"], "Anomalie confirmée après vérification manuelle.")
        self.assertIsNotNone(data["date_examen"])

    def test_anomalies_summary_endpoint(self):
        DetectionAnomalieIA.objects.create(
            id_appel_offre=999, id_soumission=1,
            type_anomalie="SIMILARITE_PRIX",
            niveau_severite="ELEVEE", score_confiance=Decimal("0.85"),
            details="test",
        )
        DetectionAnomalieIA.objects.create(
            id_appel_offre=999, id_soumission=2,
            type_anomalie="PRIX_ANORMALEMENT_BAS",
            niveau_severite="MOYEN", score_confiance=Decimal("0.80"),
            details="test",
        )

        response = self.client.get("/ia/anomalies/appel/999/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id_appel_offre"], 999)
        self.assertEqual(data["total_anomalies"], 2)
        self.assertIn("score_risque", data)
        self.assertIn("niveau_risque", data)
        self.assertIn("anomalies", data)

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

    @patch("ia_service.services.integrations.requests.patch")
    @patch("ia_service.services.integrations.requests.get")
    @patch("ia_service.services.integrations.settings.INTERNAL_SERVICE_TOKEN", "ia-internal-token")
    def test_verifier_conformite_auto_fetches_required_and_provided_docs(self, mock_get, mock_patch):
        def build_json_response(payload, status_code=200):
            response = MagicMock()
            response.status_code = status_code
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            return response

        mock_get.side_effect = [
            build_json_response([
                {"id_document": 501, "id_appel_offres": 77},
                {"id_document": 502, "id_appel_offres": 77},
            ]),
            build_json_response(
                {
                    "results": [
                        {"id_document": 501, "nom": "registre_commerce.pdf", "type_document": "pdf", "ia_verif_statut": "VALID"},
                        {"id_document": 502, "nom": "attestation_fiscale.pdf", "type_document": "pdf", "ia_verif_statut": "VALID"},
                    ]
                }
            ),
            build_json_response(
                {
                    "results": [
                        {"id_document": 9001, "nom": "rc.pdf", "type_document": "pdf", "ia_verif_statut": "VALID"},
                    ]
                }
            ),
        ]

        ok_patch = MagicMock()
        ok_patch.status_code = 200
        ok_patch.raise_for_status.return_value = None
        mock_patch.return_value = ok_patch

        payload = {
            "id_appel_offre": 77,
            "provided_document_ids": [9001],
            "perform_ocr": False,
        }

        response = self.client.post("/ia/conformite/verifier-soumission-auto/1200", payload, format="json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["conformite_statut"], "PIECES_MANQUANTES")
        self.assertEqual(data["analysis_context"]["required_document_ids"], [501, 502])
        self.assertEqual(data["analysis_context"]["provided_document_ids"], [9001])
        self.assertIn("attestation_fiscale", data["conformite_rapport"]["missing_documents"])

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_patch.call_count, 2)

    @patch("ia_service.services.integrations.requests.patch")
    @patch("ia_service.services.integrations.requests.get")
    @patch("ia_service.views.extract_document_text")
    @patch("ia_service.views.fetch_document_binary")
    @patch("ia_service.services.integrations.settings.INTERNAL_SERVICE_TOKEN", "ia-internal-token")
    def test_verifier_conformite_auto_with_ocr_enabled(self, mock_fetch_binary, mock_extract_text, mock_get, mock_patch):
        def build_json_response(payload, status_code=200):
            response = MagicMock()
            response.status_code = status_code
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            return response

        # required IDs + required metadata + provided metadata
        mock_get.side_effect = [
            build_json_response([
                {"id_document": 501, "id_appel_offres": 77},
            ]),
            build_json_response(
                {
                    "results": [
                        {"id_document": 501, "nom": "registre_commerce.pdf", "type_document": "pdf", "ia_verif_statut": "VALID"},
                    ]
                }
            ),
            build_json_response(
                {
                    "results": [
                        {"id_document": 9001, "nom": "scan_piece.bin", "type_document": "bin", "ia_verif_statut": "VALID"},
                    ]
                }
            ),
        ]

        mock_fetch_binary.return_value = {"ok": True, "content": b"binary"}
        mock_extract_text.return_value = {"text": "registre de commerce", "engine": "tesseract", "used": True}

        ok_patch = MagicMock()
        ok_patch.status_code = 200
        ok_patch.raise_for_status.return_value = None
        mock_patch.return_value = ok_patch

        payload = {
            "id_appel_offre": 77,
            "provided_document_ids": [9001],
            "perform_ocr": True,
        }

        response = self.client.post("/ia/conformite/verifier-soumission-auto/1201", payload, format="json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["conformite_statut"], "CONFORME")
        self.assertEqual(data["analysis_context"]["ocr"]["enabled"], True)
        self.assertEqual(data["analysis_context"]["ocr"]["processed"], 1)
        self.assertEqual(data["analysis_context"]["ocr"]["succeeded"], 1)

        mock_fetch_binary.assert_called_once_with(9001)
        mock_extract_text.assert_called_once()

    @patch("ia_service.services.integrations.requests.get")
    def test_detecter_anomalies_auto_fetches_soumissions(self, mock_get):
        """Test auto-detection endpoint fetches soumissions from service."""
        def build_json_response(payload, status_code=200):
            response = MagicMock()
            response.status_code = status_code
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            return response

        mock_get.side_effect = [
            # First call: fetch soumissions
            build_json_response({
                "results": [
                    {"id_soumission": 1, "montant_financier": "100000.00", "id_soumissionnaire": 10},
                    {"id_soumission": 2, "montant_financier": "100050.00", "id_soumissionnaire": 20},
                    {"id_soumission": 3, "montant_financier": "100025.00", "id_soumissionnaire": 30},
                ]
            }),
            # Second call: fetch appel details for montant_estime
            build_json_response({
                "id_appel_offre": 200,
                "montant_estime": "120000.00",
            }),
        ]

        response = self.client.post(
            "/ia/anomalies/detecter-auto",
            {"id_appel_offre": 200},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("soumissions_analysees", data)
        self.assertEqual(data["soumissions_analysees"], 3)
        self.assertIn("summary", data)

    @patch("ia_service.services.integrations.requests.get")
    def test_detecter_saucissonnage_auto_fetches_appels(self, mock_get):
        """Test auto saucissonnage endpoint fetches appels from service."""
        def build_json_response(payload, status_code=200):
            response = MagicMock()
            response.status_code = status_code
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            return response

        mock_get.return_value = build_json_response({
            "results": [
                {
                    "id_appel_offre": 1,
                    "id_service_contractant": 10,
                    "titre": "Achat materiel lot 1",
                    "montant_estime": "5000000",
                    "date_publication": "2025-01-10",
                    "type_procedure": "consultation",
                },
                {
                    "id_appel_offre": 2,
                    "id_service_contractant": 10,
                    "titre": "Achat materiel lot 2",
                    "montant_estime": "5500000",
                    "date_publication": "2025-01-20",
                    "type_procedure": "consultation",
                },
            ]
        })

        response = self.client.post(
            "/ia/saucissonnage/detecter-auto",
            {"id_service_contractant": 10},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("appels_analyses", data)
        self.assertIn("summary", data)