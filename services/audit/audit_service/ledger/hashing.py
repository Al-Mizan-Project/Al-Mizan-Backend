import hashlib
import json
from .models import AuditLog

def canonicalize_payload(payload: dict) -> bytes:
    """
    Deterministic JSON encoding for hashing.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

def to_bytes(value) -> bytes:
    """
    Normalize memoryview/None/bytes to bytes.
    """
    if value is None:
        return b"\x00" * 32
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)

def compute_hash(previous_hash: bytes, payload: dict) -> bytes:
    """
    Compute SHA256 hash of previous_hash + canonicalized payload.
    """
    canonical_payload = canonicalize_payload(payload)
    return hashlib.sha256(to_bytes(previous_hash) + canonical_payload).digest()

def compute_chain_hash(payload_hash: bytes, previous_hash: bytes | None) -> bytes:
    """
    Compute the chain hash for a record given its payload hash and previous hash.
    If previous_hash is None, treat as genesis (all zeros).
    """
    prev = to_bytes(previous_hash)
    return hashlib.sha256(prev + to_bytes(payload_hash)).digest()

def compute_record_hash(record: "AuditLog") -> dict:
    payload = {
        "utilisateur_id": record.utilisateur_id,
        "action": record.action,
        "entite_type": record.entite_type,
        "entite_id": record.entite_id,
        "adresse_ip": record.adresse_ip,
        "details_action": record.details_action or {},
    }

    previous_hash = to_bytes(record.hash_precedent)
    payload_hash = compute_hash(previous_hash, payload)
    chain_hash = compute_chain_hash(payload_hash, previous_hash)

    return {"payload_hash": payload_hash, "chain_hash": chain_hash}