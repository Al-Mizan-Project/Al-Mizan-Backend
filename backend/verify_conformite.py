"""Quick smoke test for conformite imports and basic logic."""
import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from ia_service.services.conformite import (
    DOCUMENT_TYPE_SYNONYMS,
    _normalize_text,
    _exact_match_document_type,
    infer_document_type_from_text,
    infer_document_type_from_metadata,
    build_required_documents_from_metadata,
    build_provided_documents_from_metadata,
    run_conformite_check,
    _truncate_ocr_for_matching,
)

print("=== conformite.py imports OK ===")
print(f"Canonical types: {list(DOCUMENT_TYPE_SYNONYMS.keys())}")
print(f"Count: {len(DOCUMENT_TYPE_SYNONYMS)} types")

# Test normalization
print("\n=== Normalization ===")
print(f"French accents: {repr(_normalize_text('déclaration de probité'))}")
print(f"Arabic preserved: {repr(_normalize_text('العرض التقني'))}")
print(f"Mixed: {repr(_normalize_text('offre technique العرض التقني'))}")
print(f"Empty: {repr(_normalize_text(''))}")

# Test exact match - French
print("\n=== Exact Match (French) ===")
print(f"offre technique -> {_exact_match_document_type('offre technique')}")
print(f"memoire technique -> {_exact_match_document_type('memoire technique')}")
print(f"offre financiere -> {_exact_match_document_type('offre financiere')}")
print(f"declaration de probite -> {_exact_match_document_type('declaration de probite')}")
print(f"declaration a souscrire -> {_exact_match_document_type('declaration a souscrire')}")
print(f"unknown doc xyz -> {repr(_exact_match_document_type('unknown doc xyz'))}")

# Test exact match - Arabic
print("\n=== Exact Match (Arabic) ===")
ar_tests = [
    ("العرض التقني", "offre_technique"),
    ("المذكرة التقنية", "offre_technique"),
    ("العرض المالي", "offre_financiere"),
    ("التصريح بالاكتتاب", "declaration_souscrire"),
    ("تصريح النزاهة", "declaration_probite"),
]
all_pass = True
for text, expected in ar_tests:
    result = _exact_match_document_type(text)
    status = "PASS" if result == expected else "FAIL"
    if result != expected:
        all_pass = False
    print(f"  {status}: '{text}' -> {result} (expected {expected})")

# Test conformite check
print("\n=== Conformite Check ===")
status, report = run_conformite_check(
    ["offre_technique", "offre_financiere", "declaration_probite"],
    [
        {"type_document": "offre_technique", "is_valid": True},
        {"type_document": "offre_financiere", "is_valid": True},
    ],
)
print(f"Status: {status} (expected PIECES_MANQUANTES)")
print(f"Missing: {report['missing_documents']}")
print(f"Duplicates: {report['duplicate_documents']}")

status2, report2 = run_conformite_check(
    ["offre_technique"],
    [
        {"type_document": "offre_technique", "is_valid": True},
        {"type_document": "offre_technique", "is_valid": True},
    ],
)
print(f"\nDuplicate test - Status: {status2}, Duplicates: {report2['duplicate_documents']}")

# Test truncation
print("\n=== OCR Truncation ===")
print(f"Short text: {repr(_truncate_ocr_for_matching('hello'))}")
print(f"Long text truncated to 10: len={len(_truncate_ocr_for_matching('x' * 1000, 10))}")

print("\n=== ALL SMOKE TESTS PASSED ===" if all_pass else "\n=== SOME TESTS FAILED ===")
