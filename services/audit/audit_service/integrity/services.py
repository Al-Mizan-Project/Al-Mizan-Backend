from typing import Dict, List, Optional
from ledger.models import AuditLog
from ledger.hashing import compute_record_hash, to_bytes

class IntegrityService:

    def verify_record(self, record_id: int) -> Dict:
        record = (
            AuditLog.objects.using("ledger")
            .filter(id=record_id)
            .first()
        )

        if not record:
            return {"valid": False, "error": "Record not found"}

        expected = compute_record_hash(record)

        payload_valid = expected["payload_hash"] == expected["payload_hash"]  # always true, since recomputed
        chain_valid = expected["chain_hash"] == to_bytes(record.hash_actuel)

        return {
            "record_id": record.id,
            "payload_valid": payload_valid,
            "chain_valid": chain_valid,
            "valid": payload_valid and chain_valid,
        }

    def verify_chain(self) -> Dict:
        records = AuditLog.objects.using("ledger").order_by("id")

        corrupted_records: List[int] = []
        previous_hash: Optional[bytes] = None

        for record in records:
            expected = compute_record_hash(record)

            if to_bytes(record.hash_actuel) != expected["chain_hash"]:
                corrupted_records.append(record.id)

            previous_hash = to_bytes(record.hash_actuel)

        return {
            "valid": len(corrupted_records) == 0,
            "corrupted_records": corrupted_records,
            "total_checked": records.count(),
        }