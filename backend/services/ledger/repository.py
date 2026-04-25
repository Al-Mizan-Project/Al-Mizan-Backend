from typing import Optional
from django.db import transaction
from .models import AuditLog


class AuditLedgerRepository:

    def get_last_hash(self) -> bytes:
        last_log = (
            AuditLog.objects.using("ledger")
            .only("hash_actuel")
            .order_by("-id")
            .first()
        )
        if last_log:
            return bytes(last_log.hash_actuel)
        return b"\x00" * 32

    @transaction.atomic(using="ledger")
    def create_log(
        self,
        utilisateur_id: int,
        action: str,
        entite_type: str,
        entite_id: int,
        adresse_ip: Optional[str],
        details_action: dict,
        previous_hash: bytes,
        current_hash: bytes,
    ) -> AuditLog:

        return AuditLog.objects.using("ledger").create(
            utilisateur_id=utilisateur_id,
            action=action,
            entite_type=entite_type,
            entite_id=entite_id,
            adresse_ip=adresse_ip,
            details_action=details_action,
            hash_precedent=previous_hash,
            hash_actuel=current_hash,
        )

    def get_logs_ordered(self):
        return AuditLog.objects.using("ledger").order_by("id")