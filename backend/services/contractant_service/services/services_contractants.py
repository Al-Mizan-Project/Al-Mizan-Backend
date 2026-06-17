from rest_framework.exceptions import NotFound

from contractant_service.models import ServiceContractant

from .cache import bump_cache_version


def services_contractants_queryset():
    return ServiceContractant.objects.order_by("id_service")


def get_service_or_404(service_id):
    service = ServiceContractant.objects.filter(id_service=service_id).first()
    if not service:
        raise NotFound("Service contractant not found")
    return service


def list_service_membre_ids(service_id):
    """Return distinct id_membre values across all commissions of a service."""
    service = get_service_or_404(service_id)

    from contractant_service.models import MembresCommissionEvaluation, MembresCommissionInterne

    eval_ids = list(
        MembresCommissionEvaluation.objects.filter(
            id_comission__id_service=service,
        ).values_list("id_membre", flat=True).distinct()
    )
    
    interne_ids = list(
        MembresCommissionInterne.objects.filter(
            id_commision_interne__id_service=service,
        ).values_list("id_membre", flat=True).distinct()
    )
    
    all_ids = list(eval_ids) + list(interne_ids)
    return list(dict.fromkeys(all_ids))
