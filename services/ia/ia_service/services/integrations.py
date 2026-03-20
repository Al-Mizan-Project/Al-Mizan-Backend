import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _base_url(url: str) -> str:
    return (url or "").rstrip("/")


def _extract_list_payload(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return results
    return []


def _internal_headers() -> dict:
    """Build internal service authentication headers."""
    headers = {}
    internal_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
    if internal_token:
        headers["X-Internal-Service-Token"] = internal_token
    return headers


# ---------------------------------------------------------------------------
# Appels service integrations
# ---------------------------------------------------------------------------
def fetch_appel_required_document_ids(id_appel_offre: int):
    base = _base_url(settings.APPELS_SERVICE_URL)
    endpoint = f"{base}/appels-offres/{id_appel_offre}/documents"

    try:
        response = requests.get(endpoint, timeout=settings.REMOTE_SERVICE_TIMEOUT)
        response.raise_for_status()
        payload = _extract_list_payload(response.json())
        document_ids = sorted(
            {
                int(item.get("id_document"))
                for item in payload
                if item.get("id_document") is not None
            }
        )
        return {
            "ok": True,
            "status_code": response.status_code,
            "document_ids": document_ids,
            "raw_count": len(payload),
        }
    except Exception as exc:
        logger.warning("Failed to fetch required documents for appel=%s: %s", id_appel_offre, exc)
        return {"ok": False, "error": str(exc), "document_ids": []}


def fetch_appel_details(id_appel_offre: int):
    """Fetch full details of an appel d'offres."""
    base = _base_url(settings.APPELS_SERVICE_URL)
    endpoint = f"{base}/appels-offres/{id_appel_offre}"

    try:
        response = requests.get(
            endpoint,
            headers=_internal_headers(),
            timeout=settings.REMOTE_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return {"ok": True, "appel": data}
    except Exception as exc:
        logger.warning("Failed to fetch appel details for id=%s: %s", id_appel_offre, exc)
        return {"ok": False, "error": str(exc), "appel": None}


def fetch_appels_by_service_contractant(id_service_contractant: int, params: dict = None):
    """Fetch all appels d'offres for a given service contractant."""
    base = _base_url(settings.APPELS_SERVICE_URL)
    endpoint = f"{base}/services-contractants/{id_service_contractant}/appels-offres"

    try:
        response = requests.get(
            endpoint,
            params=params or {},
            headers=_internal_headers(),
            timeout=settings.REMOTE_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        payload = _extract_list_payload(response.json())
        return {"ok": True, "appels": payload}
    except Exception as exc:
        logger.warning(
            "Failed to fetch appels for service_contractant=%s: %s",
            id_service_contractant,
            exc,
        )
        return {"ok": False, "error": str(exc), "appels": []}


# ---------------------------------------------------------------------------
# Soumissions service integrations
# ---------------------------------------------------------------------------
def fetch_soumissions_for_appel(id_appel_offre: int):
    """
    Fetch all soumissions for a given appel d'offres.
    Uses the /appels-offres/{appel_id}/soumissions endpoint.
    """
    base = _base_url(settings.SOUMISSIONS_SERVICE_URL)
    endpoint = f"{base}/api/appels-offres/{id_appel_offre}/soumissions"

    try:
        response = requests.get(
            endpoint,
            headers=_internal_headers(),
            timeout=settings.REMOTE_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        payload = _extract_list_payload(response.json())
        return {"ok": True, "soumissions": payload}
    except Exception as exc:
        logger.warning(
            "Failed to fetch soumissions for appel=%s: %s",
            id_appel_offre,
            exc,
        )
        return {"ok": False, "error": str(exc), "soumissions": []}


# ---------------------------------------------------------------------------
# Documents service integrations
# ---------------------------------------------------------------------------
def fetch_documents_metadata(document_ids):
    normalized_ids = []
    for value in document_ids or []:
        try:
            normalized_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    normalized_ids = sorted(set(normalized_ids))
    if not normalized_ids:
        return {"ok": True, "documents": [], "missing_ids": []}

    base = _base_url(settings.DOCUMENTS_SERVICE_URL)
    endpoint = f"{base}/api/documents/search/"

    try:
        response = requests.get(
            endpoint,
            params={"ids": ",".join(str(doc_id) for doc_id in normalized_ids)},
            timeout=settings.REMOTE_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        payload = _extract_list_payload(response.json())
        by_id = {
            int(item["id_document"]): item
            for item in payload
            if item.get("id_document") is not None
        }
        documents = [by_id[doc_id] for doc_id in normalized_ids if doc_id in by_id]
        missing_ids = [doc_id for doc_id in normalized_ids if doc_id not in by_id]
        return {
            "ok": True,
            "status_code": response.status_code,
            "documents": documents,
            "missing_ids": missing_ids,
        }
    except Exception as exc:
        logger.warning("Failed to fetch documents metadata for ids=%s: %s", normalized_ids, exc)
        return {"ok": False, "error": str(exc), "documents": [], "missing_ids": normalized_ids}


def fetch_document_binary(id_document: int):
    base = _base_url(settings.DOCUMENTS_SERVICE_URL)
    endpoint = f"{base}/api/documents/{int(id_document)}/"

    try:
        response = requests.get(endpoint, timeout=settings.REMOTE_SERVICE_TIMEOUT)
        response.raise_for_status()
        return {
            "ok": True,
            "status_code": response.status_code,
            "content": response.content,
            "content_type": response.headers.get("Content-Type", ""),
        }
    except Exception as exc:
        logger.warning("Failed to fetch binary document id=%s: %s", id_document, exc)
        return {"ok": False, "error": str(exc), "content": b"", "content_type": ""}


# ---------------------------------------------------------------------------
# Write-back integrations (patching other services)
# ---------------------------------------------------------------------------
def patch_soumission_conformite(id_soumission: int, conformite_statut: str, conformite_rapport):
    base = _base_url(settings.SOUMISSIONS_SERVICE_URL)
    endpoint = f"{base}/api/soumissions/{id_soumission}/conformite/"
    payload = {
        "conformite_statut": conformite_statut,
        "conformite_rapport": conformite_rapport,
    }

    try:
        response = requests.patch(
            endpoint,
            json=payload,
            headers=_internal_headers(),
            timeout=settings.REMOTE_SERVICE_TIMEOUT,
        )
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