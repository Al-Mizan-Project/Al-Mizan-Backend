import logging
import json

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _base_url(url: str) -> str:
    return (url or "").rstrip("/")


def patch_soumission_conformite(id_soumission: int, conformite_statut: str, conformite_rapport):
    base = _base_url(settings.SOUMISSIONS_SERVICE_URL)
    endpoint = f"{base}/api/soumissions/{id_soumission}/conformite/"
    payload = {
        "conformite_statut": conformite_statut,
        "conformite_rapport": conformite_rapport,
    }
    headers = {}
    internal_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
    if internal_token:
        headers["X-Internal-Service-Token"] = internal_token

    try:
        response = requests.patch(endpoint, json=payload, headers=headers, timeout=settings.REMOTE_SERVICE_TIMEOUT)
        response.raise_for_status()
        return {"ok": True, "status_code": response.status_code}
    except Exception as exc:
        logger.warning("Failed to patch soumission conformity for id=%s: %s", id_soumission, exc)
        return {"ok": False, "error": str(exc)}


def patch_document_ia_metadata(id_document: int, ia_verif_statut: str, ia_verif_details):
    base = _base_url(settings.DOCUMENTS_SERVICE_URL)
    endpoint = f"{base}/api/documents/{id_document}/ia-metadata/"
    if isinstance(ia_verif_details, (dict, list)):
        serialized_details = json.dumps(ia_verif_details, ensure_ascii=True)
    elif ia_verif_details is None:
        serialized_details = ""
    else:
        serialized_details = str(ia_verif_details)

    payload = {
        "ia_verif_statut": ia_verif_statut,
        "ia_verif_details": serialized_details,
    }
    try:
        response = requests.patch(endpoint, json=payload, timeout=settings.REMOTE_SERVICE_TIMEOUT)
        response.raise_for_status()
        return {"ok": True, "status_code": response.status_code}
    except Exception as exc:
        logger.warning("Failed to patch document metadata for id=%s: %s", id_document, exc)
        return {"ok": False, "error": str(exc)}