import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _timeout():
    return getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)


# ── Appels Service ──────────────────────────────────────────────

def validate_appel_offre(id_appel_offre):
    """Return (exists: bool, data: dict|None). Degrades gracefully."""
    url = f"{settings.APPELS_SERVICE_URL}/appels-offres/{id_appel_offre}"
    try:
        resp = requests.get(url, timeout=_timeout())
        if resp.status_code == 200:
            return True, resp.json()
        if resp.status_code == 404:
            return False, None
        logger.warning("Appels service returned %s for AO %s", resp.status_code, id_appel_offre)
        return True, None  # can't confirm → allow
    except requests.RequestException as exc:
        logger.warning("Appels service unreachable: %s", exc)
        return True, None  # graceful degradation


def fetch_appel_private_key(id_appel_offre):
    """
    Fetch the RSA private key (PEM) for an appel d'offre from the Appels service.
    Returns PEM bytes or None on failure.
    """
    url = f"{settings.APPELS_SERVICE_URL}/appels-offres/{id_appel_offre}/private-key"
    token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
    headers = {"X-Internal-Service-Token": token} if token else {}
    try:
        resp = requests.get(url, headers=headers, timeout=_timeout())
        if resp.status_code == 200:
            data = resp.json()
            pem = data.get("private_key_pem")
            if pem:
                return pem.encode("utf-8") if isinstance(pem, str) else pem
        logger.warning(
            "Appels service returned %s for private key of AO %s",
            resp.status_code,
            id_appel_offre,
        )
        return None
    except requests.RequestException as exc:
        logger.warning("Appels service unreachable for private key: %s", exc)
        return None


# ── Documents Service ───────────────────────────────────────────

def validate_document_ids(document_ids):
    """Return (all_valid: bool, missing_ids: list). Degrades gracefully."""
    if not document_ids:
        return True, []
    ids_param = ",".join(str(d) for d in document_ids)
    url = f"{settings.DOCUMENTS_SERVICE_URL}/api/documents/search/"
    try:
        resp = requests.get(url, params={"ids": ids_param}, timeout=_timeout())
        if resp.status_code == 200:
            data = resp.json()
            results = data if isinstance(data, list) else data.get("results", [])
            found_ids = {item.get("id_document") for item in results}
            missing = [d for d in document_ids if d not in found_ids]
            return len(missing) == 0, missing
        logger.warning("Documents service returned %s", resp.status_code)
        return True, []
    except requests.RequestException as exc:
        logger.warning("Documents service unreachable: %s", exc)
        return True, []


# ── Evaluations Service ─────────────────────────────────────────

def fetch_evaluations_for_soumission(soumission_id):
    """Fetch evaluations from Evaluations service. Returns list."""
    url = f"{settings.EVALUATIONS_SERVICE_URL}/soumissions/{soumission_id}/evaluations"
    try:
        resp = requests.get(url, timeout=_timeout())
        if resp.status_code == 200:
            return resp.json()
        return []
    except requests.RequestException as exc:
        logger.warning("Evaluations service unreachable: %s", exc)
        return []


def create_evaluation(payload):
    """
    Proxy evaluation creation to Evaluations service.
    Returns (status_code, response_body).
    """
    url = f"{settings.EVALUATIONS_SERVICE_URL}/evaluations"
    try:
        resp = requests.post(url, json=payload, timeout=_timeout())
        return resp.status_code, resp.json()
    except requests.RequestException as exc:
        logger.error("Evaluations service unreachable: %s", exc)
        return 503, {"error": f"Service d'évaluations indisponible: {exc}"}


# ── MinIO (Object Storage) ──────────────────────────────────────

def download_encrypted_file(minio_url):
    """
    Download an encrypted file from MinIO / object storage.
    Returns bytes or None on failure.
    """
    try:
        resp = requests.get(minio_url, timeout=30)
        if resp.status_code == 200:
            return resp.content
        logger.error("MinIO returned %s for %s", resp.status_code, minio_url)
        return None
    except requests.RequestException as exc:
        logger.error("MinIO unreachable for %s: %s", minio_url, exc)
        return None


# ── Audit Service ───────────────────────────────────────────────

def send_audit_log(utilisateur_id, action, entite_type, entite_id,
                   adresse_ip=None, details_action=None):
    """
    Send an audit log entry to the Audit service.
    Fire-and-forget with graceful degradation (logs warning on failure).
    """
    url = f"{settings.AUDIT_SERVICE_URL}/journaux-audit/create/"
    payload = {
        "utilisateur_id": utilisateur_id,
        "action": action,
        "entite_type": entite_type,
        "entite_id": str(entite_id),
    }
    if adresse_ip:
        payload["adresse_ip"] = adresse_ip
    if details_action:
        payload["details_action"] = details_action
    try:
        resp = requests.post(url, json=payload, timeout=_timeout())
        if resp.status_code == 201:
            log_id = resp.json().get("log_id")
            logger.info("Audit log created: %s (action=%s)", log_id, action)
            return log_id
        logger.warning(
            "Audit service returned %s for action %s: %s",
            resp.status_code,
            action,
            resp.text,
        )
        return None
    except requests.RequestException as exc:
        logger.warning("Audit service unreachable: %s", exc)
        return None
