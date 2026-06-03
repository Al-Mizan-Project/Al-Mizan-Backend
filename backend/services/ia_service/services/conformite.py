"""
Conformité analysis — document type recognition and presence validation.

Supports the four document types required for conformité checking:
  - offre_technique
  - offre_financiere
  - declaration_souscrire
  - declaration_probite

Uses a **hybrid matching strategy**:
  1. **Exact match** (fast path) — substring matching against known
     French + Arabic aliases.
  2. **Semantic similarity fallback** — multilingual embeddings via
     ``embedding.semantic_match_document_type()`` when exact match fails.
"""

import logging
import re
import unicodedata
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synonym dictionary — French + Arabic (MSA) aliases
# ORDER MATTERS: déclarations before offres to avoid false positives.
# ---------------------------------------------------------------------------
DOCUMENT_TYPE_SYNONYMS = {
    # ── Déclarations (checked first to avoid "soumission" false positives) ──
    "declaration_souscrire": [
        # French
        "declaration a souscrire",
        "declaration souscrire",
        "declaration_souscrire",
        "souscrire",
        "lettre de soumission",
        "engagement du soumissionnaire",
        "declaration de souscription",
        # Arabic (MSA)
        "التصريح بالاكتتاب",
        "رسالة التعهد",
        "التزام المتعهد",
        "تصريح الاكتتاب",
    ],
    "declaration_probite": [
        # French
        "declaration de probite",
        "declaration_probite",
        "probite",
        "engagement de probite",
        "attestation de probite",
        # Arabic (MSA)
        "تصريح النزاهة",
        "اقرار بالنزاهة",
        "شهادة النزاهة",
        "التزام بالنزاهة",
        "النزاهة",
    ],
    # ── Offres ──────────────────────────────────────────────────────────────
    "offre_technique": [
        # French
        "offre technique",
        "offre_technique",
        "fiche technique",
        "memoire technique",
        "dossier technique",
        "proposition technique",
        "specifications techniques",
        # Arabic (MSA)
        "العرض التقني",
        "المذكرة التقنية",
        "الملف التقني",
        "المواصفات التقنية",
        "الاقتراح التقني",
    ],
    "offre_financiere": [
        # French
        "offre financiere",
        "offre_financiere",
        "bordereau des prix",
        "bordereau prix unitaires",
        "bpu",
        "devis quantitatif",
        "devis estimatif",
        "montant de l offre",
        "soumission financiere",
        "proposition financiere",
        # Arabic (MSA)
        "العرض المالي",
        "كشف الاسعار",
        "جدول الاسعار",
        "التقدير المالي",
    ],
}


# ---------------------------------------------------------------------------
# Text normalisation — preserves Arabic characters
# ---------------------------------------------------------------------------
def _normalize_text(value: str) -> str:
    """
    Normalize text for matching.

    * Unicode NFKD decomposition + strip combining marks (accents)
    * Lowercase Latin characters
    * Preserve Arabic character ranges (U+0600–U+06FF, U+0750–U+077F)
    * Collapse whitespace
    """
    text = unicodedata.normalize("NFKD", str(value or ""))
    # Remove combining marks (diacritics / accents) but keep Arabic base chars
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    # Keep: a-z, 0-9, Arabic (U+0600-U+06FF, U+0750-U+077F)
    text = re.sub(r"[^a-z0-9\u0600-\u06FF\u0750-\u077F]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Document type inference — hybrid: exact match + semantic fallback
# ---------------------------------------------------------------------------
def _exact_match_document_type(*values: str) -> str:
    """
    Try to match text against ``DOCUMENT_TYPE_SYNONYMS`` using substring
    matching.  Returns the canonical type or ``""`` if no match.
    """
    normalized_values = [_normalize_text(item) for item in values if str(item).strip()]
    if not normalized_values:
        return ""

    haystack = f" {' '.join(normalized_values)} "

    for canonical, aliases in DOCUMENT_TYPE_SYNONYMS.items():
        for alias in aliases:
            token = _normalize_text(alias)
            if token and f" {token} " in haystack:
                return canonical

    return ""


def _truncate_ocr_for_matching(ocr_text: str, max_chars: int = 500) -> str:
    """
    Return only the first *max_chars* characters of OCR text.

    Semantic matching should NOT process full documents — only filenames,
    titles, and leading OCR snippets.
    """
    if not ocr_text:
        return ""
    return ocr_text[:max_chars].strip()


def infer_document_type_from_text(*values: str) -> str:
    """
    Infer the canonical document type from one or more text values.

    **Step 1 — Exact match** (fast, ~0 ms):
        Substring matching against ``DOCUMENT_TYPE_SYNONYMS``.

    **Step 2 — Semantic similarity** (fallback, ~5-15 ms):
        Uses multilingual embeddings if exact match fails.

    Returns the canonical type (e.g. ``"offre_technique"``) or ``""``.
    """
    # Step 1: exact match
    exact = _exact_match_document_type(*values)
    if exact:
        return exact

    # Step 2: semantic similarity fallback
    # Combine values into a single query (truncated)
    combined_parts = []
    for val in values:
        stripped = str(val).strip()
        if stripped:
            combined_parts.append(stripped)
    if not combined_parts:
        return ""

    combined = " ".join(combined_parts)
    # Truncate to avoid processing full documents
    combined = _truncate_ocr_for_matching(combined)

    try:
        from .embedding import semantic_match_document_type

        result = semantic_match_document_type(combined)
        if result:
            logger.debug(
                "Semantic fallback matched: %r → %s", combined[:60], result
            )
        return result
    except Exception as exc:
        logger.warning("Semantic matching failed, returning empty: %s", exc)
        return ""


def infer_document_type_from_metadata(document: Dict) -> str:
    """
    Infer document type from metadata fields.

    Uses: ``type_document_label``, ``nom`` (filename), ``type_document``,
    and a **truncated** ``ocr_text`` snippet.
    """
    ocr_text = _truncate_ocr_for_matching(
        str(document.get("ocr_text", ""))
    )
    return infer_document_type_from_text(
        str(document.get("type_document_label", "")),
        str(document.get("nom", "")),
        str(document.get("type_document", "")),
        ocr_text,
    )


# ---------------------------------------------------------------------------
# Build required / provided document lists
# ---------------------------------------------------------------------------
def build_required_documents_from_metadata(documents: List[Dict]) -> List[str]:
    """Infer canonical types from required document metadata."""
    inferred = [infer_document_type_from_metadata(doc) for doc in documents]
    return sorted({item for item in inferred if item})


def build_provided_documents_from_metadata(
    documents: List[Dict],
    enforce_validity_checks: bool = True,
) -> List[Dict]:
    """
    Build the provided documents list with inferred canonical types.

    Each entry contains:
      - ``id_document``
      - ``type_document`` (canonical)
      - ``is_valid``
    """
    provided = []
    for doc in documents:
        inferred_type = infer_document_type_from_metadata(doc)
        if not inferred_type:
            continue

        provided.append(
            {
                "id_document": doc.get("id_document"),
                "type_document": inferred_type,
                "is_valid": True,
            }
        )

    return provided


# ---------------------------------------------------------------------------
# Conformité check — required vs. provided validation
# ---------------------------------------------------------------------------
def _extract_doc_type(doc: Dict) -> str:
    """Extract the canonical type from a provided document dict."""
    return _normalize_text(str(doc.get("type_document", "")))


def run_conformite_check(
    required_documents: List[str],
    provided_documents: List[Dict],
) -> Tuple[str, Dict]:
    """
    Compare required documents against provided documents.

    Checks:
      - Missing documents (required but not provided)
      - Invalid documents (provided but flagged as invalid)
      - Duplicate documents (same canonical type provided multiple times)

    Does NOT check: fraud, anomalies, authenticity, ownership.

    Returns ``(status, report)`` where status is one of:
      - ``"CONFORME"``
      - ``"PIECES_MANQUANTES"``
      - ``"NON_CONFORME"``
    """
    required_set = {
        _normalize_text(item) for item in required_documents if str(item).strip()
    }

    provided_map: Dict[str, Dict] = {}
    invalid_docs: List[str] = []
    duplicate_docs: List[str] = []

    for doc in provided_documents:
        doc_type = _extract_doc_type(doc)
        if not doc_type:
            continue

        # Track duplicates
        if doc_type in provided_map:
            duplicate_docs.append(doc_type)

        provided_map[doc_type] = doc

        if doc.get("is_valid") is False:
            invalid_docs.append(doc_type)

    missing_docs = sorted(
        [doc for doc in required_set if doc not in provided_map]
    )

    # Determine status
    if missing_docs:
        conformite_status = "PIECES_MANQUANTES"
    elif invalid_docs:
        conformite_status = "NON_CONFORME"
    else:
        conformite_status = "CONFORME"

    report = {
        "required_count": len(required_set),
        "provided_count": len(provided_map),
        "missing_documents": missing_docs,
        "invalid_documents": sorted(set(invalid_docs)),
        "duplicate_documents": sorted(set(duplicate_docs)),
        "conformite_statut": conformite_status,
    }
    return conformite_status, report