from rest_framework.exceptions import NotFound

from acteurs_service.models import OperateurEconomique


def operateurs_queryset():
    return OperateurEconomique.objects.order_by("id_operateur_economique")


def get_operateur_or_404(operateur_id):
    operateur = OperateurEconomique.objects.filter(id_operateur_economique=operateur_id).first()
    if not operateur:
        raise NotFound("Operateur economique not found")
    return operateur


def get_operateur_by_nif_or_404(nif):
    operateur = OperateurEconomique.objects.filter(nif=nif).first()
    if not operateur:
        raise NotFound("Operateur economique not found")
    return operateur
