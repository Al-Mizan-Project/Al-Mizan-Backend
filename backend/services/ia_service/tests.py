from decimal import Decimal
from unittest.mock import MagicMock, patch
 
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
 
from ia_service.models import DetectionAnomalieIA
from ia_service.services.anomalies import (
    detect_anomalies_appel,
    detect_anomalies_soumission,
    generate_anomaly_summary,
    _compute_score_severite,
    _score_to_niveau,
    ANOMALY_POINTS,
)
from ia_service.services.ocr import extract_document_text, extract_documents_text_parallel
from ia_service.services.saucissonnage import detect_saucissonnage
 
 
# ===========================================================================
# Helpers
# ===========================================================================
def _make_soumission(id_soumission, montant, id_soumissionnaire=None,
                     date_soumission=None, **kwargs):
    s = {
        "id_soumission": id_soumission,
        "montant_financier": montant,
    }
    if id_soumissionnaire is not None:
        s["id_soumissionnaire"] = id_soumissionnaire
    if date_soumission is not None:
        s["date_soumission"] = date_soumission
    s.update(kwargs)
    return s
 
 
BASE_APPEL = {
    "montant_estime": "1000000",
    "date_limite_soumission": "2099-12-31T23:59:59",
}
 
 
# ===========================================================================
# Unit Tests — individual rule detectors
# ===========================================================================
class TestMontantManquant(TestCase):
    def test_null_montant_after_opening_date(self):
        """NULL montant_financier after deadline → MONTANT_FINANCIER_MANQUANT."""
        soumission = {"id_soumission": 1, "montant_financier": None}
        appel = {
            "montant_estime": "1000000",
            "date_limite_soumission": "2000-01-01T00:00:00",  # past
        }
        result = detect_anomalies_soumission(soumission, appel, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("MONTANT_FINANCIER_MANQUANT", types)
 
    def test_null_montant_before_opening_does_not_flag(self):
        """NULL montant_financier before deadline is expected — no anomaly."""
        soumission = {"id_soumission": 1, "montant_financier": None}
        appel = {
            "montant_estime": "1000000",
            "date_limite_soumission": "2099-12-31T23:59:59",  # future
        }
        result = detect_anomalies_soumission(soumission, appel, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("MONTANT_FINANCIER_MANQUANT", types)
 
 
class TestMontantInvalid(TestCase):
    def test_zero_montant_flagged(self):
        soumission = _make_soumission(1, "0")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("MONTANT_INVALID", types)
 
    def test_negative_montant_flagged(self):
        soumission = _make_soumission(1, "-5000")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("MONTANT_INVALID", types)
 
    def test_valid_positive_montant_not_flagged(self):
        soumission = _make_soumission(1, "500000")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("MONTANT_INVALID", types)
 
 
class TestMontantTropEleve(TestCase):
    def test_ratio_above_3x_flagged(self):
        """montant = 3 100 000 > 3× 1 000 000 → MONTANT_TROP_ELEVE."""
        soumission = _make_soumission(1, "3100000")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("MONTANT_TROP_ELEVE", types)
 
    def test_ratio_exactly_3x_not_flagged(self):
        soumission = _make_soumission(1, "3000000")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("MONTANT_TROP_ELEVE", types)
 
 
class TestMontantTropBas(TestCase):
    def test_below_70pct_flagged(self):
        """montant = 600 000 < 70% of 1 000 000 → MONTANT_TROP_BAS."""
        soumission = _make_soumission(1, "600000")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("MONTANT_TROP_BAS", types)
 
    def test_exactly_70pct_not_flagged(self):
        soumission = _make_soumission(1, "700000")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("MONTANT_TROP_BAS", types)
 
 
class TestSoumissionHorsDelai(TestCase):
    def test_after_deadline_flagged(self):
        soumission = _make_soumission(1, "900000",
                                      date_soumission="2026-05-15T14:32:00")
        appel = {
            "montant_estime": "1000000",
            "date_limite_soumission": "2026-05-10T23:59:00",
        }
        result = detect_anomalies_soumission(soumission, appel, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("SOUMISSION_HORS_DELAI", types)
 
    def test_before_deadline_not_flagged(self):
        soumission = _make_soumission(1, "900000",
                                      date_soumission="2026-05-09T10:00:00")
        appel = {
            "montant_estime": "1000000",
            "date_limite_soumission": "2026-05-10T23:59:00",
        }
        result = detect_anomalies_soumission(soumission, appel, [soumission])
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("SOUMISSION_HORS_DELAI", types)
 
 
class TestPrixAnormauxIQR(TestCase):
    """PRIX_ANORMALEMENT_ELEVE / BAS require ≥ 3 soumissions."""
 
    def _run(self, all_soumissions, target_id):
        target = next(s for s in all_soumissions if s["id_soumission"] == target_id)
        appel = {"montant_estime": "1000000", "date_limite_soumission": "2099-12-31"}
        return detect_anomalies_soumission(target, appel, all_soumissions)
 
    def test_high_outlier_flagged(self):
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "1100000"),
            _make_soumission(3, "1050000"),
            _make_soumission(4, "1080000"),
            _make_soumission(5, "5000000"),  # outlier high
        ]
        result = self._run(soumissions, 5)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("PRIX_ANORMALEMENT_ELEVE", types)
 
    def test_low_outlier_flagged(self):
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "1100000"),
            _make_soumission(3, "1050000"),
            _make_soumission(4, "100000"),   # outlier low
        ]
        result = self._run(soumissions, 4)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("PRIX_ANORMALEMENT_BAS", types)
 
    def test_normal_price_not_flagged(self):
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "1100000"),
            _make_soumission(3, "1050000"),
        ]
        result = self._run(soumissions, 1)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("PRIX_ANORMALEMENT_ELEVE", types)
        self.assertNotIn("PRIX_ANORMALEMENT_BAS", types)
 
    def test_less_than_3_soumissions_no_outlier_check(self):
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "9000000"),  # only 2 → no IQR check
        ]
        result = self._run(soumissions, 2)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("PRIX_ANORMALEMENT_ELEVE", types)
 
 
class TestDispersionAnormale(TestCase):
    def test_low_cv_flagged(self):
        """CV < 2% with ≥ 3 soumissions → DISPERSION_ANORMALE."""
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "1001000"),
            _make_soumission(3, "1000500"),
            _make_soumission(4, "1000200"),
        ]
        result = detect_anomalies_appel(soumissions, BASE_APPEL)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("DISPERSION_ANORMALE", types)
 
    def test_high_cv_not_flagged(self):
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "1300000"),
            _make_soumission(3, "1600000"),
        ]
        result = detect_anomalies_appel(soumissions, BASE_APPEL)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("DISPERSION_ANORMALE", types)
 
    def test_less_than_3_no_dispersion_check(self):
        soumissions = [
            _make_soumission(1, "1000000"),
            _make_soumission(2, "1001000"),
        ]
        result = detect_anomalies_appel(soumissions, BASE_APPEL)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("DISPERSION_ANORMALE", types)
 
 
class TestRotationSoumissionnaires(TestCase):
    def _historical_wins(self):
        return [
            {"id_appel_offre": 1, "id_soumissionnaire": 10, "id_soumission": 100},
            {"id_appel_offre": 2, "id_soumissionnaire": 20, "id_soumission": 200},
            {"id_appel_offre": 3, "id_soumissionnaire": 10, "id_soumission": 300},
            {"id_appel_offre": 4, "id_soumissionnaire": 20, "id_soumission": 400},
            {"id_appel_offre": 5, "id_soumissionnaire": 10, "id_soumission": 500},
            {"id_appel_offre": 6, "id_soumissionnaire": 20, "id_soumission": 600},
        ]
 
    def test_rotation_detected(self):
        soumissions = [
            _make_soumission(1, "900000", id_soumissionnaire=10),
            _make_soumission(2, "950000", id_soumissionnaire=20),
        ]
        result = detect_anomalies_appel(soumissions, BASE_APPEL,
                                        historical_wins=self._historical_wins())
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertIn("ROTATION_SOUMISSIONNAIRES", types)
 
    def test_rotation_requires_3_appels(self):
        """With only 2 historical wins, no rotation alert."""
        soumissions = [_make_soumission(1, "900000", id_soumissionnaire=10)]
        wins = [
            {"id_appel_offre": 1, "id_soumissionnaire": 10, "id_soumission": 100},
            {"id_appel_offre": 2, "id_soumissionnaire": 20, "id_soumission": 200},
        ]
        result = detect_anomalies_appel(soumissions, BASE_APPEL, historical_wins=wins)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("ROTATION_SOUMISSIONNAIRES", types)
 
    def test_no_historical_wins_no_rotation(self):
        soumissions = [_make_soumission(1, "900000", id_soumissionnaire=10)]
        result = detect_anomalies_appel(soumissions, BASE_APPEL)
        types = [a["type_anomalie"] for a in result["anomalies"]]
        self.assertNotIn("ROTATION_SOUMISSIONNAIRES", types)
 
 
# ===========================================================================
# Unit Tests — Scoring engine
# ===========================================================================
class TestScoringEngine(TestCase):
    def test_score_capped_at_100(self):
        anomalies = [
            {"type_anomalie": "MONTANT_FINANCIER_MANQUANT"},  # 20
            {"type_anomalie": "MONTANT_INVALID"},              # 20
            {"type_anomalie": "SOUMISSION_HORS_DELAI"},        # 20
            {"type_anomalie": "ROTATION_SOUMISSIONNAIRES"},    # 20
            {"type_anomalie": "MONTANT_TROP_ELEVE"},           # 10
            {"type_anomalie": "MONTANT_TROP_BAS"},             # 10
        ]
        score = _compute_score_severite(anomalies)
        self.assertEqual(score, 100)
 
    def test_score_zero_for_no_anomalies(self):
        self.assertEqual(_compute_score_severite([]), 0)
 
    def test_niveau_mapping(self):
        self.assertEqual(_score_to_niveau(0), "FAIBLE")
        self.assertEqual(_score_to_niveau(20), "FAIBLE")
        self.assertEqual(_score_to_niveau(21), "MOYEN")
        self.assertEqual(_score_to_niveau(50), "MOYEN")
        self.assertEqual(_score_to_niveau(51), "ÉLEVÉ")
        self.assertEqual(_score_to_niveau(80), "ÉLEVÉ")
        self.assertEqual(_score_to_niveau(81), "CRITIQUE")
        self.assertEqual(_score_to_niveau(100), "CRITIQUE")
 
    def test_severity_error_vs_warning(self):
        soumission = {"id_soumission": 1, "montant_financier": None}
        appel = {
            "montant_estime": "1000000",
            "date_limite_soumission": "2000-01-01T00:00:00",
        }
        result = detect_anomalies_soumission(soumission, appel, [soumission])
        errors = [a for a in result["anomalies"] if a["niveau_severite"] == "ERROR"]
        self.assertGreaterEqual(len(errors), 1)
 
    def test_score_confiance_in_valid_range(self):
        soumission = _make_soumission(1, "-100")
        result = detect_anomalies_soumission(soumission, BASE_APPEL, [soumission])
        for a in result["anomalies"]:
            self.assertGreaterEqual(float(a["score_confiance"]), 0.90)
            self.assertLessEqual(float(a["score_confiance"]), 1.00)
 
 
# ===========================================================================
# Unit Tests — detect_anomalies_appel
# ===========================================================================
class TestDetectAnomaliesAppel(TestCase):
    def test_returns_correct_structure(self):
        soumissions = [_make_soumission(i, str(1000000 + i * 1000)) for i in range(1, 5)]
        result = detect_anomalies_appel(soumissions, BASE_APPEL)
        self.assertIn("anomalies", result)
        self.assertIn("total_soumissions_analysees", result)
        self.assertIn("resume_global", result)
        self.assertEqual(result["total_soumissions_analysees"], 4)
 
    def test_empty_soumissions(self):
        result = detect_anomalies_appel([], BASE_APPEL)
        self.assertEqual(result["anomalies"], [])
        self.assertEqual(result["total_soumissions_analysees"], 0)
 
    def test_all_invalid_amounts_flagged(self):
        soumissions = [
            _make_soumission(1, "0"),
            _make_soumission(2, "-1000"),
            _make_soumission(3, "500000"),
        ]
        result = detect_anomalies_appel(soumissions, BASE_APPEL)
        types_by_id = {}
        for a in result["anomalies"]:
            types_by_id.setdefault(a["id_soumission"], []).append(a["type_anomalie"])
 
        self.assertIn("MONTANT_INVALID", types_by_id.get(1, []))
        self.assertIn("MONTANT_INVALID", types_by_id.get(2, []))
        self.assertNotIn("MONTANT_INVALID", types_by_id.get(3, []))

    def test_detects_mixed_anomalies_and_updates_global_summary(self):
        soumissions = [
            _make_soumission(1, "3500000", date_soumission="2026-05-09T10:00:00"),
            _make_soumission(2, "600000", date_soumission="2026-05-11T09:00:00"),
            _make_soumission(3, "1000000", date_soumission="2026-05-09T11:00:00"),
        ]
        appel = {
            "montant_estime": "1000000",
            "date_limite_soumission": "2026-05-10T23:59:00",
        }

        result = detect_anomalies_appel(soumissions, appel)
        types_by_id = {}
        for anomaly in result["anomalies"]:
            types_by_id.setdefault(anomaly["id_soumission"], []).append(anomaly["type_anomalie"])

        self.assertIn("MONTANT_TROP_ELEVE", types_by_id.get(1, []))
        self.assertIn("MONTANT_TROP_BAS", types_by_id.get(2, []))
        self.assertIn("SOUMISSION_HORS_DELAI", types_by_id.get(2, []))
        self.assertEqual(result["resume_global"]["total_anomalies"], 3)
        self.assertEqual(result["resume_global"]["score_severite_global"], 40)
        self.assertEqual(result["resume_global"]["niveau_global"], "MOYEN")

    def test_detects_rotation_for_current_soumissionnaires(self):
        soumissions = [
            _make_soumission(1, "900000", id_soumissionnaire=10),
            _make_soumission(2, "950000", id_soumissionnaire=20),
            _make_soumission(3, "1100000", id_soumissionnaire=30),
        ]
        historical_wins = [
            {"id_appel_offre": 1, "id_soumissionnaire": 10, "id_soumission": 100},
            {"id_appel_offre": 2, "id_soumissionnaire": 20, "id_soumission": 200},
            {"id_appel_offre": 3, "id_soumissionnaire": 10, "id_soumission": 300},
            {"id_appel_offre": 4, "id_soumissionnaire": 20, "id_soumission": 400},
        ]

        result = detect_anomalies_appel(soumissions, BASE_APPEL, historical_wins=historical_wins)
        rotation_anomalies = [
            anomaly for anomaly in result["anomalies"]
            if anomaly["type_anomalie"] == "ROTATION_SOUMISSIONNAIRES"
        ]

        self.assertEqual({a["id_soumission"] for a in rotation_anomalies}, {1, 2})
        for anomaly in rotation_anomalies:
            self.assertEqual(anomaly["soumissions_impliquees"], [1, 2])
        self.assertEqual(result["resume_global"]["total_anomalies"], 2)
 
 
# ===========================================================================
# Unit Tests — generate_anomaly_summary
# ===========================================================================
class TestGenerateAnomalySummary(TestCase):
    def test_summary_structure(self):
        anomalies = [
            {"type_anomalie": "MONTANT_FINANCIER_MANQUANT", "niveau_severite": "ERROR",
             "score_confiance": 1.0},
            {"type_anomalie": "PRIX_ANORMALEMENT_BAS", "niveau_severite": "WARNING",
             "score_confiance": 0.90},
        ]
        summary = generate_anomaly_summary(anomalies, soumissions_count=5)
        self.assertEqual(summary["total_anomalies"], 2)
        self.assertEqual(summary["nb_errors"], 1)
        self.assertEqual(summary["nb_warnings"], 1)
        self.assertIn("score_severite_global", summary)
        self.assertIn("niveau_global", summary)
        self.assertIn("recommandation", summary)
        self.assertIn("repartition_par_type", summary)
 
    def test_score_and_niveau_correct(self):
        anomalies = [
            {"type_anomalie": "MONTANT_FINANCIER_MANQUANT", "niveau_severite": "ERROR", "score_confiance": 1.0},
            {"type_anomalie": "SOUMISSION_HORS_DELAI", "niveau_severite": "ERROR", "score_confiance": 1.0},
            {"type_anomalie": "ROTATION_SOUMISSIONNAIRES", "niveau_severite": "WARNING", "score_confiance": 0.90},
        ]
        summary = generate_anomaly_summary(anomalies, soumissions_count=3)
        # 20 + 20 + 20 = 60 → ÉLEVÉ
        self.assertEqual(summary["score_severite_global"], 60)
        self.assertEqual(summary["niveau_global"], "ÉLEVÉ")


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
        self.authenticate_internal()

    def authenticate_internal(self):
        self.client.credentials(HTTP_X_INTERNAL_SERVICE_TOKEN=settings.INTERNAL_SERVICE_TOKEN)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    @patch("ia_service.services.integrations.requests.get")
    def test_detecter_anomalies_creates_records(self, mock_get):
        def build_json_response(payload, status_code=200):
            response = MagicMock()
            response.status_code = status_code
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            return response

        mock_get.side_effect = [
            build_json_response({"id_soumission": 1, "montant_financier": "100000.00", "signature_document": "abc123"}),
            build_json_response({"id_appel_offre": 101, "montant_estime": "120000.00"}),
            build_json_response({
                "results": [
                    {"id_soumission": 1, "montant_financier": "100000.00", "signature_document": "abc123"},
                    {"id_soumission": 2, "montant_financier": "100200.00", "signature_document": "abc123"},
                ]
            }),
        ]
        payload = {
            "id_appel_offre": 101,
            "id_soumission": 1,
        }
        response = self.client.post("/ia/anomalies/detecter", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("resume", data)
        self.assertIn("anomalies", data)

    @patch("ia_service.services.integrations.requests.get")
    def test_detecter_anomalies_returns_summary(self, mock_get):
        def build_json_response(payload, status_code=200):
            response = MagicMock()
            response.status_code = status_code
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            return response

        soumissions = [
            {"id_soumission": 1, "montant_financier": "100000"},
            {"id_soumission": 2, "montant_financier": "100050"},
            {"id_soumission": 3, "montant_financier": "100025"},
        ]
        mock_get.side_effect = [
            build_json_response(soumissions[0]),
            build_json_response({"id_appel_offre": 102, "montant_estime": "120000"}),
            build_json_response({"results": soumissions}),
        ]
        payload = {
            "id_appel_offre": 102,
            "id_soumission": 1,
        }
        response = self.client.post("/ia/anomalies/detecter", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        summary = data.get("resume", {})
        self.assertIn("score_severite_global", summary)
        self.assertIn("niveau_global", summary)
        self.assertIn("total_anomalies", summary)

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
            type_anomalie="PRIX_ANORMALEMENT_BAS",
            niveau_severite="WARNING", score_confiance=Decimal("0.85"),
            details="test", statut_examen="EN_ATTENTE",
        )
        # Create saucissonnage anomaly
        DetectionAnomalieIA.objects.create(
            id_appel_offre=1,
            type_anomalie="SAUCISSONNAGE_CUMUL_SEUIL",
            niveau_severite="WARNING", score_confiance=Decimal("0.95"),
            details="test", statut_examen="EN_ATTENTE",
        )

        # Filter collusion only
        response = self.client.get("/ia/anomalies?categorie=collusion")
        self.assertEqual(response.status_code, 200)
        data = response.json()["anomalies"]
        for item in data:
            self.assertFalse(item["type_anomalie"].startswith("SAUCISSONNAGE"))

        # Filter saucissonnage only
        response = self.client.get("/ia/anomalies?categorie=saucissonnage")
        self.assertEqual(response.status_code, 200)
        data = response.json()["anomalies"]
        for item in data:
            self.assertTrue(item["type_anomalie"].startswith("SAUCISSONNAGE"))

    def test_anomalie_statut_examen_patch_with_comment(self):
        record = DetectionAnomalieIA.objects.create(
            id_appel_offre=1, id_soumission=1,
            type_anomalie="PRIX_ANORMALEMENT_BAS",
            niveau_severite="WARNING", score_confiance=Decimal("0.85"),
            details="test", statut_examen="EN_ATTENTE",
        )
        payload = {
            "statut_examen": "VALIDE",
            "commentaire_examen": "Anomalie confirmée après vérification manuelle.",
        }
        response = self.client.patch(
            f"/ia/anomalies/{record.id_detection_anomalie_ia}/statut-examen",
            payload, format="json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["statut_examen"], "VALIDE")
        self.assertEqual(data["commentaire_examen"], "Anomalie confirmée après vérification manuelle.")
        self.assertIsNotNone(data["date_examen"])

    def test_anomalies_summary_endpoint(self):
        DetectionAnomalieIA.objects.create(
            id_appel_offre=999, id_soumission=1,
            type_anomalie="PRIX_ANORMALEMENT_ELEVE",
            niveau_severite="WARNING", score_confiance=Decimal("0.85"),
            details="test",
        )
        DetectionAnomalieIA.objects.create(
            id_appel_offre=999, id_soumission=2,
            type_anomalie="PRIX_ANORMALEMENT_BAS",
            niveau_severite="WARNING", score_confiance=Decimal("0.80"),
            details="test",
        )

        response = self.client.get("/ia/anomalies/appel/999/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id_appel_offre"], 999)
        self.assertEqual(data["resume"]["total_anomalies"], 2)
        self.assertIn("score_severite_global", data["resume"])
        self.assertIn("niveau_global", data["resume"])
        self.assertIn("repartition", data)

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
        self.authenticate_internal()
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
        self.authenticate_internal()
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
        self.authenticate_internal()
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
    @patch("ia_service.views.extract_documents_text_parallel")
    @patch("ia_service.views.fetch_document_binary")
    @patch("ia_service.services.integrations.settings.INTERNAL_SERVICE_TOKEN", "ia-internal-token")
    def test_verifier_conformite_auto_with_ocr_enabled(self, mock_fetch_binary, mock_extract_parallel, mock_get, mock_patch):
        self.authenticate_internal()
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
        mock_extract_parallel.return_value = [
            {"text": "registre de commerce", "engine": "tesseract", "used": True}
        ]

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
        mock_extract_parallel.assert_called_once()

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
        self.assertIn("total_soumissions_analysees", data)
        self.assertEqual(data["total_soumissions_analysees"], 3)
        self.assertIn("resume_global", data)

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
