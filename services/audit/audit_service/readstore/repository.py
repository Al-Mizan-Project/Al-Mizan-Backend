from typing import Optional
from django.core.paginator import Paginator
from .models import AuditLogRead


class AuditReadRepository:

    def get_by_id(self, log_id: int) -> Optional[AuditLogRead]:
        return (
            AuditLogRead.objects.using("read")
            .filter(id=log_id)
            .first()
        )

    def get_by_user(self, user_id: int, page: int = 1, page_size: int = 50):
        queryset = (
            AuditLogRead.objects.using("read")
            .filter(utilisateur_id=user_id)
            .order_by("-horodatage")
        )
        return self._paginate(queryset, page, page_size)

    def get_by_entity(
        self,
        entite_type: str,
        entite_id: int,
        page: int = 1,
        page_size: int = 50,
    ):
        queryset = (
            AuditLogRead.objects.using("read")
            .filter(entite_type=entite_type, entite_id=entite_id)
            .order_by("-horodatage")
        )
        return self._paginate(queryset, page, page_size)

    def list_logs(self, filters: dict, page: int = 1, page_size: int = 50):
        queryset = AuditLogRead.objects.using("read").all()

        if "utilisateur_id" in filters:
            queryset = queryset.filter(utilisateur_id=filters["utilisateur_id"])

        if "entite_type" in filters:
            queryset = queryset.filter(entite_type=filters["entite_type"])

        if "entite_id" in filters:
            queryset = queryset.filter(entite_id=filters["entite_id"])

        if "date_from" in filters:
            queryset = queryset.filter(horodatage__gte=filters["date_from"])

        if "date_to" in filters:
            queryset = queryset.filter(horodatage__lte=filters["date_to"])

        queryset = queryset.order_by("-horodatage")

        return self._paginate(queryset, page, page_size)

    def _paginate(self, queryset, page: int, page_size: int):
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        return {
            "items": list(page_obj.object_list),
            "total": paginator.count,
            "num_pages": paginator.num_pages,
            "current_page": page_obj.number,
        }