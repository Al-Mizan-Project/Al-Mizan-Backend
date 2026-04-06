from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound

from acteurs_service.models import Membre, Organisation


SERVICE_CONTRACTANT_TYPES = (
    "service contractant",
    "service-contractant",
    "service_contractant",
    "services contractants",
    "services-contractants",
    "services_contractants",
)
SERVICE_CONTRACTANT_PRIMARY_TYPE = "service contractant"


def organisations_queryset():
    return Organisation.objects.order_by("id_organisation")


def get_organisation_or_404(organisation_id):
    organisation = Organisation.objects.filter(id_organisation=organisation_id).first()
    if not organisation:
        raise NotFound("Organisation not found")
    return organisation


def organisation_membres_queryset(organisation_id):
    get_organisation_or_404(organisation_id)
    return Membre.objects.filter(id_organisation=organisation_id).order_by("id_membre")


def is_service_contractant_type(value):
    return str(value).strip().lower() in SERVICE_CONTRACTANT_TYPES


def service_contractants_queryset():
    filters = Q(pk__isnull=True)
    for type_entite in SERVICE_CONTRACTANT_TYPES:
        filters |= Q(type_entite__iexact=type_entite)
    return organisations_queryset().filter(filters)


def get_service_contractant_or_404(service_id):
    service_contractant = service_contractants_queryset().filter(id_organisation=service_id).first()
    if not service_contractant:
        raise NotFound("Service contractant not found")
    return service_contractant


def service_contractant_membres_queryset(service_id):
    get_service_contractant_or_404(service_id)
    return Membre.objects.filter(id_organisation=service_id).order_by("id_membre")


@transaction.atomic
def delete_organisation(organisation_id):
    organisation = get_organisation_or_404(organisation_id)
    Membre.objects.filter(id_organisation=organisation.id_organisation).update(id_organisation=None)
    organisation.delete()
