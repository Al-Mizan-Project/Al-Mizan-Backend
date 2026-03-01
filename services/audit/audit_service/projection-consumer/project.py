from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone
 
 
class ProjectionError(Exception):
    """Raised when a valid event cannot be projected. Do not retry silently."""
    pass
 
 
def project_audit_log_created(event: dict) -> bool:
    """
    Project an 'audit_log.created' event into the AuditLogRead read model.
 
    Returns True if a new row was inserted, False if the row already existed
    (idempotent re-delivery).
 
    Raises ProjectionError on validation failures.
    Raises Django/psycopg2 exceptions on DB failures (let caller handle).
    """
    # Late import: requires django_setup.setup() to have been called.
    from readstore.models import AuditLogRead
 
    # ── Validate required fields ────────────────────────────────────────
    required = ['id', 'utilisateur_id', 'action', 'entite_type',
                'entite_id', 'horodatage']
    missing = [f for f in required if f not in event]
    if missing:
        raise ProjectionError(
            f"Event is missing required fields: {missing}. "
            f"Event keys present: {list(event.keys())}"
        )
 
    # ── Parse timestamp ─────────────────────────────────────────────────
    horodatage = parse_datetime(str(event['horodatage']))
    if horodatage is None:
        raise ProjectionError(
            f"Cannot parse 'horodatage': {event['horodatage']!r}. "
            f"Expected ISO 8601 string (e.g. '2024-01-15T10:30:00+00:00')."
        )
    if timezone.is_naive(horodatage):
        horodatage = timezone.make_aware(horodatage, timezone.utc)
 
    # ── Upsert ──────────────────────────────────────────────────────────
    with transaction.atomic(using='read'):
        _, created = AuditLogRead.objects.using('read').update_or_create(
            id=int(event['id']),
            defaults={
                'utilisateur_id': int(event['utilisateur_id']),
                'action':         str(event['action'])[:100],
                'entite_type':    str(event['entite_type'])[:50],
                'entite_id':      int(event['entite_id']),
                'horodatage':     horodatage,
                'adresse_ip':     event.get('adresse_ip'),
                'details_action': event.get('details_action', {}),
            }
        )
    return created
 
 
# ── Event router ────────────────────────────────────────────────────────
# Map event_type strings to handler functions.
# Extend this dict when you add new event types.
EVENT_HANDLERS = {
    'audit_log.created': project_audit_log_created,
}
 
 
def dispatch_event(event: dict, event_type: str = None) -> bool:
    """
    Route an event dict to the correct projection handler based on event_type.
    event_type can be passed explicitly or read from the event dict itself.
    """
    etype = event_type or event.get('event_type') or 'audit_log.created'
    handler = EVENT_HANDLERS.get(etype)
    if handler is None:
        # Unknown event types are logged and skipped, not failed.
        # This is correct: future event types should not crash the consumer.
        print(f"[projection] Skipping unknown event_type: {etype!r}")
        return False
    return handler(event)
