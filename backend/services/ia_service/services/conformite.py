import re
import unicodedata
from typing import Dict, List, Tuple


DOCUMENT_TYPE_SYNONYMS = {
    # ── Documents prioritaires — ORDRE IMPORTANT (premier match gagne) ─
    # Les déclarations AVANT les offres pour éviter les faux positifs
    "declaration_souscrire": [
        "declaration a souscrire",
        "declaration souscrire",
        "declaration_souscrire",
        "souscrire",
        "lettre de soumission",
        "engagement du soumissionnaire",
    ],
    "declaration_probite": [
        "declaration de probite",
        "declaration_probite",
        "probite",
        "engagement de probite",
        "attestation de probite",
    ],
    "offre_technique": [
        "offre technique",
        "offre_technique",
        "fiche technique",
        "memoire technique",
        "dossier technique",
        "proposition technique",
        "specifications techniques",
    ],
    "offre_financiere": [
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
    ],
    # ── Documents administratifs ───────────────────────────────────────
    "rc": ["rc", "registre commerce", "registre de commerce", "registre_commerce", "extrait du registre"],
    "nif": ["nif", "numero identification fiscale", "identification fiscale", "carte fiscale"],
    "nis": ["nis", "numero identification statistique", "identification statistique"],
    "ai": ["ai", "article imposition", "attestation imposition"],
    "cnas": ["cnas", "attestation cnas", "certificat cnas", "mise a jour cnas"],
    "casnos": ["casnos", "attestation casnos", "certificat casnos"],
    "attestation_fiscale": [
        "attestation fiscale",
        "regularite fiscale",
        "quitus fiscal",
        "extrait role",
    ],
    "garantie_bancaire": [
        "garantie bancaire",
        "caution de soumission",
        "caution bancaire",
        "caution provisoire",
        "caution definitive",
    ],
    "certificat_non_faillite": [
        "non faillite",
        "certificat de non faillite",
        "non faillite non reglement judiciaire",
    ],
}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def infer_document_type_from_text(*values: str) -> str:
    normalized_values = [_normalize_text(item) for item in values if str(item).strip()]
    haystack = f" {' '.join(normalized_values)} "

    for canonical, aliases in DOCUMENT_TYPE_SYNONYMS.items():
        for alias in aliases:
            token = _normalize_text(alias)
            if token and f" {token} " in haystack:
                return canonical

    return normalized_values[0] if normalized_values else ""


def infer_document_type_from_metadata(document: Dict) -> str:
    return infer_document_type_from_text(
        str(document.get("type_document_label", "")),
        str(document.get("nom", "")),
        str(document.get("type_document", "")),
        str(document.get("ocr_text", "")),
    )


def build_required_documents_from_metadata(documents: List[Dict]) -> List[str]:
    inferred = [infer_document_type_from_metadata(doc) for doc in documents]
    return sorted({item for item in inferred if item})


def build_provided_documents_from_metadata(documents: List[Dict], enforce_validity_checks: bool = True) -> List[Dict]:
    provided = []
    for doc in documents:
        inferred_type = infer_document_type_from_metadata(doc)
        if not inferred_type:
            continue

        is_valid = True

        provided.append(
            {
                "id_document": doc.get("id_document"),
                "type_document": inferred_type,
                "is_valid": bool(is_valid),
            }
        )

    return provided


def _extract_doc_type(doc: Dict) -> str:
    return _normalize_text(str(doc.get("type_document", "")))


def run_conformite_check(required_documents: List[str], provided_documents: List[Dict]) -> Tuple[str, Dict]:
    required_set = {_normalize_text(item) for item in required_documents if str(item).strip()}
    provided_map = {}
    invalid_docs = []

    for doc in provided_documents:
        doc_type = _extract_doc_type(doc)
        if not doc_type:
            continue
        provided_map[doc_type] = doc
        if doc.get("is_valid") is False:
            invalid_docs.append(doc_type)

    missing_docs = sorted([doc for doc in required_set if doc not in provided_map])

    if missing_docs:
        status = "PIECES_MANQUANTES"
    elif invalid_docs:
        status = "NON_CONFORME"
    else:
        status = "CONFORME"

    report = {
        "required_count": len(required_set),
        "provided_count": len(provided_map),
        "missing_documents": missing_docs,
        "invalid_documents": sorted(set(invalid_docs)),
        "conformite_statut": status,
    }
    return status, report