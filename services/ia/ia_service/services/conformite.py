from typing import Dict, List, Tuple


def _extract_doc_type(doc: Dict) -> str:
    return str(doc.get("type_document", "")).strip().lower()


def run_conformite_check(required_documents: List[str], provided_documents: List[Dict]) -> Tuple[str, Dict]:
    required_set = {item.strip().lower() for item in required_documents if str(item).strip()}
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