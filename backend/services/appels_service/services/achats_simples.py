from django.db.models import Q
from rest_framework.exceptions import NotFound

from appels_service.models import AchatSimple


def achats_simples_queryset(statut=None, service_id=None, search=None):
    queryset = AchatSimple.objects.order_by("-created_at")
    if statut:
        queryset = queryset.filter(statut=statut)
    if service_id is not None:
        queryset = queryset.filter(id_service_contractant=service_id)
    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search)
            | Q(objet__icontains=search)
            | Q(description__icontains=search)
        )
    return queryset


def achats_simples_by_service_queryset(service_id):
    return AchatSimple.objects.filter(id_service_contractant=service_id).order_by("-created_at")


def get_achat_simple_or_404(achat_id):
    obj = AchatSimple.objects.filter(id_achat_simple=achat_id).first()
    if not obj:
        raise NotFound("Achat simple not found")
    return obj
