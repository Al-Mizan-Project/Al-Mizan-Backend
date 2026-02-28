from typing import Dict
from .repository import AuditReadRepository


class AuditReadService:

    def __init__(self):
        self.repository = AuditReadRepository()

    def get_log(self, log_id: int):
        return self.repository.get_by_id(log_id)

    def get_logs_by_user(self, user_id: int, page: int, page_size: int):
        return self.repository.get_by_user(user_id, page, page_size)

    def get_logs_by_entity(
        self,
        entite_type: str,
        entite_id: int,
        page: int,
        page_size: int,
    ):
        return self.repository.get_by_entity(
            entite_type,
            entite_id,
            page,
            page_size,
        )

    def list_logs(self, filters: Dict, page: int, page_size: int):
        return self.repository.list_logs(filters, page, page_size)