from typing import Dict
from .repository import AuditReadRepository
from django.core.cache import cache

class AuditReadService:

    def __init__(self):
        self.repository = AuditReadRepository()

    def get_log(self, log_id: int):
        key = f"log:{log_id}"
        result = cache.get(key)
        if result is None:
            result = self.repository.get_by_id(log_id)
            if result:
                cache.set(key, result, timeout=300)
        return result

    def get_logs_by_user(self, user_id: int, page: int, page_size: int):
        key = f"user_logs:{user_id}:page:{page}:size:{page_size}"
        result = cache.get(key)
        if result is None:
            result = self.repository.get_by_user(user_id, page, page_size)
            cache.set(key, result, timeout=300)
        return result

    def get_logs_by_entity(
        self,
        entite_type: str,
        entite_id: int,
        page: int,
        page_size: int,
    ):
        key = f"entity_logs:{entite_type}:{entite_id}:page:{page}:size:{page_size}"
        result = cache.get(key)
        if result is None:
            result = self.repository.get_by_entity(entite_type, entite_id, page, page_size)
            cache.set(key, result, timeout=300)
        return result

    def list_logs(self, filters: Dict, page: int, page_size: int):
        key_parts = [f"{k}:{v}" for k, v in sorted(filters.items())]
        key = f"logs_list:{'-'.join(key_parts)}:page:{page}:size:{page_size}"
        result = cache.get(key)
        if result is None:
            result = self.repository.list_logs(filters, page, page_size)
            cache.set(key, result, timeout=300)
        return result