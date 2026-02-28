from typing import Dict
from django.db import transaction
from .repository import AuditLedgerRepository
from .hashing import compute_chain_hash, compute_hash


class AuditLedgerService:

    def __init__(self):
        self.repository = AuditLedgerRepository()

    from .hashing import compute_record_hash

    @transaction.atomic(using="ledger")
    def log_event(self, data: Dict) -> int:
        """
        Creates a new immutable audit log entry.
        Returns log ID.
        """

        previous_hash = self.repository.get_last_hash()

        payload = self._build_payload(data)

        payload_hash = compute_hash(previous_hash, payload)
        chain_hash = compute_chain_hash(payload_hash, previous_hash)

        log = self.repository.create_log(
            utilisateur_id=data["utilisateur_id"],
            action=data["action"],
            entite_type=data["entite_type"],
            entite_id=data["entite_id"],
            adresse_ip=data.get("adresse_ip"),
            details_action=data.get("details_action", {}),
            previous_hash=previous_hash,
            current_hash=chain_hash,
        )

        return log.id


    def _build_payload(self, data: Dict) -> Dict:
        """
        Build canonical payload for hashing.
        Only include fields relevant to integrity.
        """
        return {
            "utilisateur_id": data["utilisateur_id"],
            "action": data["action"],
            "entite_type": data["entite_type"],
            "entite_id": data["entite_id"],
            "adresse_ip": data.get("adresse_ip"),
            "details_action": data.get("details_action", {}),
        }