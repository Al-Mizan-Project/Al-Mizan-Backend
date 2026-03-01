import json
from typing import Optional
 
 
class DeserialisationError(Exception):
    """Raised when a Kafka message cannot be safely deserialised."""
    pass
 
 
def unwrap_debezium_json(raw_bytes: bytes) -> dict:
    """
    Unwrap a Debezium-produced Kafka message value into a plain Python dict.
 
    Handles two formats:
      1. Schema-wrapped:  { 'schema': {...}, 'payload': '<json string>' }
      2. Bare payload:    '<json string>'  or  { ...event fields... }
 
    Returns the innermost event dict.
    Raises DeserialisationError on any parse failure.
    """
    if not raw_bytes:
        raise DeserialisationError("Received empty message value")
 
    try:
        decoded_str: str = raw_bytes.decode('utf-8')
    except UnicodeDecodeError as e:
        raise DeserialisationError(f"UTF-8 decode failed: {e}") from e
 
    try:
        outer = json.loads(decoded_str)
    except json.JSONDecodeError as e:
        raise DeserialisationError(f"Outer JSON parse failed: {e}") from e
 
    # ── Case 1: Kafka Connect schema wrapper present ────────────────────
    if isinstance(outer, dict) and 'schema' in outer and 'payload' in outer:
        inner_raw = outer['payload']
        # The payload is itself a JSON string (Debezium serialises
        # JSONField columns as escaped strings, not embedded objects).
        if isinstance(inner_raw, str):
            try:
                return json.loads(inner_raw)
            except json.JSONDecodeError as e:
                raise DeserialisationError(
                    f"Inner payload JSON parse failed: {e}. "
                    f"Raw payload: {inner_raw[:200]}"
                ) from e
        elif isinstance(inner_raw, dict):
            # Payload is already a dict (schemas_enable=false, JSON payload)
            return inner_raw
        else:
            raise DeserialisationError(
                f"Unexpected payload type: {type(inner_raw)}"
            )
 
    # ── Case 2: No schema wrapper — outer is the event dict ────────────
    elif isinstance(outer, dict):
        return outer
 
    # ── Case 3: Outer is a raw JSON string ─────────────────────────────
    elif isinstance(outer, str):
        try:
            return json.loads(outer)
        except json.JSONDecodeError as e:
            raise DeserialisationError(f"Bare string JSON parse failed: {e}") from e
 
    else:
        raise DeserialisationError(
            f"Cannot deserialise message of type {type(outer)}"
        )
