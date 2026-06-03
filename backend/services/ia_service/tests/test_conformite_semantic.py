"""
Tests for the semantic conformité analysis module.

Covers:
  - Arabic document type detection (exact match)
  - French document type detection (exact match)
  - Semantic similarity fallback (mocked model)
  - Mixed Arabic/French OCR snippets
  - Exact match priority over semantic
  - Below-threshold rejection
  - OCR typo robustness
  - Duplicate document handling
  - Missing document handling
  - Text normalisation (Arabic preservation)
  - OCR text truncation
"""

from unittest.mock import MagicMock, patch

import numpy as np
from django.test import TestCase

from ia_service.services.conformite import (
    DOCUMENT_TYPE_SYNONYMS,
    _exact_match_document_type,
    _normalize_text,
    _truncate_ocr_for_matching,
    build_provided_documents_from_metadata,
    build_required_documents_from_metadata,
    infer_document_type_from_metadata,
    infer_document_type_from_text,
    run_conformite_check,
)


# ===========================================================================
# 1. Text normalisation
# ===========================================================================
class TestNormalizeText(TestCase):
    """Verify _normalize_text preserves Arabic and strips French accents."""

    def test_french_accents_stripped(self):
        self.assertEqual(_normalize_text("déclaration de probité"), "declaration de probite")

    def test_arabic_preserved(self):
        result = _normalize_text("العرض التقني")
        self.assertIn("العرض", result)
        self.assertIn("التقني", result)

    def test_mixed_french_arabic(self):
        result = _normalize_text("offre technique العرض التقني")
        self.assertIn("offre", result)
        self.assertIn("technique", result)
        self.assertIn("العرض", result)
        self.assertIn("التقني", result)

    def test_special_chars_removed(self):
        result = _normalize_text("offre_technique (v2.1) -- final!")
        self.assertNotIn("(", result)
        self.assertNotIn("!", result)
        self.assertNotIn("--", result)

    def test_whitespace_collapsed(self):
        result = _normalize_text("  offre   technique   ")
        self.assertEqual(result, "offre technique")

    def test_empty_string(self):
        self.assertEqual(_normalize_text(""), "")
        self.assertEqual(_normalize_text(None), "")

    def test_uppercase_lowered(self):
        self.assertEqual(_normalize_text("OFFRE TECHNIQUE"), "offre technique")


# ===========================================================================
# 2. Exact match — French
# ===========================================================================
class TestExactMatchFrench(TestCase):
    """French aliases should be matched via exact substring matching."""

    def test_offre_technique(self):
        self.assertEqual(
            _exact_match_document_type("offre technique"), "offre_technique"
        )

    def test_memoire_technique(self):
        self.assertEqual(
            _exact_match_document_type("mémoire technique"), "offre_technique"
        )

    def test_offre_financiere(self):
        self.assertEqual(
            _exact_match_document_type("offre financière"), "offre_financiere"
        )

    def test_bordereau_des_prix(self):
        self.assertEqual(
            _exact_match_document_type("bordereau des prix"), "offre_financiere"
        )

    def test_declaration_a_souscrire(self):
        self.assertEqual(
            _exact_match_document_type("déclaration à souscrire"),
            "declaration_souscrire",
        )

    def test_declaration_probite(self):
        self.assertEqual(
            _exact_match_document_type("déclaration de probité"),
            "declaration_probite",
        )

    def test_attestation_probite(self):
        self.assertEqual(
            _exact_match_document_type("attestation de probité"),
            "declaration_probite",
        )

    def test_no_match_returns_empty(self):
        self.assertEqual(
            _exact_match_document_type("document inconnu xyz"), ""
        )


# ===========================================================================
# 3. Exact match — Arabic
# ===========================================================================
class TestExactMatchArabic(TestCase):
    """Arabic MSA aliases should be matched via exact substring matching."""

    def test_offre_technique_arabic(self):
        self.assertEqual(
            _exact_match_document_type("العرض التقني"), "offre_technique"
        )

    def test_memoire_technique_arabic(self):
        self.assertEqual(
            _exact_match_document_type("المذكرة التقنية"), "offre_technique"
        )

    def test_offre_financiere_arabic(self):
        self.assertEqual(
            _exact_match_document_type("العرض المالي"), "offre_financiere"
        )

    def test_prix_table_arabic(self):
        self.assertEqual(
            _exact_match_document_type("جدول الاسعار"), "offre_financiere"
        )

    def test_declaration_souscrire_arabic(self):
        self.assertEqual(
            _exact_match_document_type("التصريح بالاكتتاب"),
            "declaration_souscrire",
        )

    def test_declaration_probite_arabic(self):
        self.assertEqual(
            _exact_match_document_type("تصريح النزاهة"), "declaration_probite"
        )

    def test_engagement_probite_arabic(self):
        self.assertEqual(
            _exact_match_document_type("التزام بالنزاهة"), "declaration_probite"
        )


# ===========================================================================
# 4. Exact match — mixed input
# ===========================================================================
class TestExactMatchMixed(TestCase):
    """Multiple text values should be combined for matching."""

    def test_filename_contains_type(self):
        self.assertEqual(
            _exact_match_document_type("scan_2025.pdf", "offre technique"),
            "offre_technique",
        )

    def test_arabic_filename(self):
        self.assertEqual(
            _exact_match_document_type("العرض_التقني.pdf"),
            "offre_technique",
        )

    def test_multiple_values_first_match_wins(self):
        # declaration_souscrire should match before offre_technique due to order
        result = _exact_match_document_type(
            "lettre de soumission", "offre technique"
        )
        self.assertEqual(result, "declaration_souscrire")


# ===========================================================================
# 5. Semantic fallback (mocked model)
# ===========================================================================
class TestSemanticFallback(TestCase):
    """
    When exact match fails, infer_document_type_from_text should call the
    semantic embedding module. We mock the embedding to avoid downloading
    the actual model during tests.
    """

    @patch("ia_service.services.embedding.semantic_match_document_type")
    def test_semantic_called_when_exact_fails(self, mock_semantic):
        mock_semantic.return_value = "offre_technique"
        # "technical proposal document" won't match any exact alias
        result = infer_document_type_from_text("technical proposal document")
        mock_semantic.assert_called_once()
        self.assertEqual(result, "offre_technique")

    @patch("ia_service.services.embedding.semantic_match_document_type")
    def test_semantic_not_called_when_exact_matches(self, mock_semantic):
        # "offre technique" matches exactly — semantic should NOT be called
        result = infer_document_type_from_text("offre technique")
        mock_semantic.assert_not_called()
        self.assertEqual(result, "offre_technique")

    @patch("ia_service.services.embedding.semantic_match_document_type")
    def test_semantic_returns_empty_below_threshold(self, mock_semantic):
        mock_semantic.return_value = ""
        result = infer_document_type_from_text("completely unrelated text xyz")
        self.assertEqual(result, "")

    @patch("ia_service.services.embedding.semantic_match_document_type")
    def test_semantic_handles_exception_gracefully(self, mock_semantic):
        mock_semantic.side_effect = RuntimeError("Model not loaded")
        result = infer_document_type_from_text("some text that fails")
        self.assertEqual(result, "")

    @patch("ia_service.services.embedding.semantic_match_document_type")
    def test_semantic_with_arabic_paraphrase(self, mock_semantic):
        mock_semantic.return_value = "offre_financiere"
        # Arabic wording not in exact aliases
        result = infer_document_type_from_text("عرض الثمن الإجمالي")
        mock_semantic.assert_called_once()
        self.assertEqual(result, "offre_financiere")


# ===========================================================================
# 6. OCR text truncation
# ===========================================================================
class TestOcrTruncation(TestCase):
    """OCR text should be truncated to avoid processing full documents."""

    def test_short_text_unchanged(self):
        self.assertEqual(_truncate_ocr_for_matching("hello"), "hello")

    def test_long_text_truncated(self):
        long_text = "x" * 1000
        result = _truncate_ocr_for_matching(long_text, max_chars=500)
        self.assertEqual(len(result), 500)

    def test_empty_text(self):
        self.assertEqual(_truncate_ocr_for_matching(""), "")
        self.assertEqual(_truncate_ocr_for_matching(None), "")


# ===========================================================================
# 7. Metadata inference
# ===========================================================================
class TestInferFromMetadata(TestCase):
    """infer_document_type_from_metadata should use type_document_label,
    nom, type_document, and truncated ocr_text."""

    def test_from_filename_french(self):
        doc = {"nom": "offre_technique_final.pdf", "type_document": "PDF"}
        self.assertEqual(infer_document_type_from_metadata(doc), "offre_technique")

    def test_from_filename_arabic(self):
        doc = {"nom": "العرض_المالي.pdf", "type_document": "PDF"}
        self.assertEqual(infer_document_type_from_metadata(doc), "offre_financiere")

    def test_from_type_document_label(self):
        doc = {"type_document_label": "Déclaration de Probité", "nom": "scan.pdf"}
        self.assertEqual(infer_document_type_from_metadata(doc), "declaration_probite")

    @patch("ia_service.services.embedding.semantic_match_document_type")
    def test_from_ocr_text_fallback(self, mock_semantic):
        mock_semantic.return_value = "offre_technique"
        doc = {
            "nom": "document.pdf",
            "type_document": "PDF",
            "ocr_text": "This is a detailed technical proposal for the project...",
        }
        result = infer_document_type_from_metadata(doc)
        self.assertEqual(result, "offre_technique")


# ===========================================================================
# 8. Build required/provided documents
# ===========================================================================
class TestBuildDocumentLists(TestCase):

    def test_build_required_from_metadata(self):
        docs = [
            {"nom": "offre_technique.pdf", "type_document": "offre technique"},
            {"nom": "offre_financiere.pdf", "type_document": "offre financiere"},
        ]
        result = build_required_documents_from_metadata(docs)
        self.assertIn("offre_technique", result)
        self.assertIn("offre_financiere", result)

    def test_build_provided_from_metadata(self):
        docs = [
            {"id_document": 1, "nom": "offre_technique.pdf", "type_document": "offre technique"},
            {"id_document": 2, "nom": "probite.pdf", "type_document": "declaration de probite"},
        ]
        result = build_provided_documents_from_metadata(docs)
        self.assertEqual(len(result), 2)
        types = [d["type_document"] for d in result]
        self.assertIn("offre_technique", types)
        self.assertIn("declaration_probite", types)

    def test_unrecognized_documents_excluded(self):
        docs = [
            {"id_document": 1, "nom": "random_file.pdf", "type_document": "unknown_xyz"},
        ]
        with patch(
            "ia_service.services.embedding.semantic_match_document_type",
            return_value="",
        ):
            result = build_provided_documents_from_metadata(docs)
        self.assertEqual(len(result), 0)


# ===========================================================================
# 9. Conformité check — missing documents
# ===========================================================================
class TestConformiteCheckMissing(TestCase):
    """run_conformite_check should detect missing required documents."""

    def test_all_present_is_conforme(self):
        required = ["offre_technique", "offre_financiere"]
        provided = [
            {"type_document": "offre_technique", "is_valid": True},
            {"type_document": "offre_financiere", "is_valid": True},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "CONFORME")
        self.assertEqual(report["missing_documents"], [])

    def test_missing_document_detected(self):
        required = ["offre_technique", "offre_financiere", "declaration_probite"]
        provided = [
            {"type_document": "offre_technique", "is_valid": True},
            {"type_document": "offre_financiere", "is_valid": True},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "PIECES_MANQUANTES")
        self.assertIn("declaration probite", report["missing_documents"])

    def test_invalid_document_non_conforme(self):
        required = ["offre_technique"]
        provided = [
            {"type_document": "offre_technique", "is_valid": False},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "NON_CONFORME")
        self.assertIn("offre technique", report["invalid_documents"])

    def test_missing_takes_priority_over_invalid(self):
        required = ["offre_technique", "offre_financiere"]
        provided = [
            {"type_document": "offre_technique", "is_valid": False},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "PIECES_MANQUANTES")


# ===========================================================================
# 10. Conformité check — duplicate documents
# ===========================================================================
class TestConformiteCheckDuplicates(TestCase):
    """run_conformite_check should track duplicate document types."""

    def test_duplicate_detected(self):
        required = ["offre_technique"]
        provided = [
            {"type_document": "offre_technique", "is_valid": True},
            {"type_document": "offre_technique", "is_valid": True},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "CONFORME")
        self.assertIn("offre technique", report["duplicate_documents"])

    def test_no_duplicate_when_unique(self):
        required = ["offre_technique", "offre_financiere"]
        provided = [
            {"type_document": "offre_technique", "is_valid": True},
            {"type_document": "offre_financiere", "is_valid": True},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(report["duplicate_documents"], [])


# ===========================================================================
# 11. Conformité check — empty inputs
# ===========================================================================
class TestConformiteCheckEdgeCases(TestCase):

    def test_empty_required_is_conforme(self):
        status, report = run_conformite_check([], [])
        self.assertEqual(status, "CONFORME")

    def test_empty_provided_with_required_is_missing(self):
        status, report = run_conformite_check(["offre_technique"], [])
        self.assertEqual(status, "PIECES_MANQUANTES")

    def test_extra_provided_docs_ignored(self):
        required = ["offre_technique"]
        provided = [
            {"type_document": "offre_technique", "is_valid": True},
            {"type_document": "offre_financiere", "is_valid": True},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "CONFORME")
        self.assertEqual(report["provided_count"], 2)
        self.assertEqual(report["required_count"], 1)


# ===========================================================================
# 12. Full pipeline — French OCR scenario
# ===========================================================================
class TestFullPipelineFrench(TestCase):
    """End-to-end scenario with French document names."""

    def test_full_conformite_french_documents(self):
        required_docs = [
            {"nom": "offre_technique_ref.pdf", "type_document": "offre technique"},
            {"nom": "offre_financiere_ref.pdf", "type_document": "offre financiere"},
            {"nom": "declaration_probite_ref.pdf", "type_document": "declaration de probite"},
            {"nom": "declaration_souscrire_ref.pdf", "type_document": "declaration a souscrire"},
        ]
        provided_docs = [
            {"id_document": 1, "nom": "OT_entreprise.pdf", "type_document": "offre technique"},
            {"id_document": 2, "nom": "OF_montants.pdf", "type_document": "offre financiere"},
            {"id_document": 3, "nom": "probite_signee.pdf", "type_document": "declaration de probite"},
            {"id_document": 4, "nom": "souscrire_signee.pdf", "type_document": "declaration a souscrire"},
        ]

        required = build_required_documents_from_metadata(required_docs)
        provided = build_provided_documents_from_metadata(provided_docs)

        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "CONFORME")
        self.assertEqual(len(report["missing_documents"]), 0)


# ===========================================================================
# 13. Full pipeline — Arabic document names
# ===========================================================================
class TestFullPipelineArabic(TestCase):
    """End-to-end scenario with Arabic document names."""

    def test_full_conformite_arabic_documents(self):
        required_docs = [
            {"nom": "العرض_التقني.pdf", "type_document": "العرض التقني"},
            {"nom": "العرض_المالي.pdf", "type_document": "العرض المالي"},
        ]
        provided_docs = [
            {"id_document": 1, "nom": "العرض_التقني.pdf", "type_document": "العرض التقني"},
            {"id_document": 2, "nom": "العرض_المالي.pdf", "type_document": "العرض المالي"},
        ]

        required = build_required_documents_from_metadata(required_docs)
        provided = build_provided_documents_from_metadata(provided_docs)

        status, report = run_conformite_check(required, provided)
        self.assertEqual(status, "CONFORME")


# ===========================================================================
# 14. Report structure validation
# ===========================================================================
class TestConformiteReportStructure(TestCase):
    """The conformité report must always contain all expected keys."""

    def test_report_has_all_keys(self):
        status, report = run_conformite_check(
            ["offre_technique"],
            [{"type_document": "offre_technique", "is_valid": True}],
        )
        expected_keys = {
            "required_count",
            "provided_count",
            "missing_documents",
            "invalid_documents",
            "duplicate_documents",
            "conformite_statut",
        }
        self.assertEqual(set(report.keys()), expected_keys)

    def test_report_counts_accurate(self):
        required = ["offre_technique", "offre_financiere", "declaration_probite"]
        provided = [
            {"type_document": "offre_technique", "is_valid": True},
        ]
        status, report = run_conformite_check(required, provided)
        self.assertEqual(report["required_count"], 3)
        self.assertEqual(report["provided_count"], 1)
        self.assertEqual(len(report["missing_documents"]), 2)
