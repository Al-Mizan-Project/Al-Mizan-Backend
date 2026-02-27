import hashlib
import json


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


def compute_hash(previous_hash: bytes, payload: dict) -> bytes:
    """
    Compute SHA256 hash of previous_hash + canonicalized payload.
    """
    canonical_payload = canonicalize_payload(payload)
    return hashlib.sha256(previous_hash + canonical_payload).digest()