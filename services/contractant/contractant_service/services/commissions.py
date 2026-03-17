from django.conf import settings
from rest_framework.exceptions import NotFound, ValidationError
import requests

from contractant_service.models import (
    CommissionEvaluation,
    CommissionExterne,
    CommissionInterne,
    MembresCommissionEvaluation,
    MembresCommissionInterne,
)

from .cache import bump_cache_version


# ── Querysets ────────────────────────────────────────────────────────


def commissions_evaluation_queryset():
    return CommissionEvaluation.objects.select_related("id_service").order_by("id_comission")


def commissions_internes_queryset():
    return CommissionInterne.objects.select_related("id_service").order_by("id_comission_interne")


def commissions_externes_queryset():
    return CommissionExterne.objects.order_by("id_comission_externe")


# ── Lookups ──────────────────────────────────────────────────────────


def get_commission_eval_or_404(commission_id):
    obj = CommissionEvaluation.objects.filter(id_comission=commission_id).first()
    if not obj:
        raise NotFound("Commission evaluation not found")
    return obj


def get_commission_interne_or_404(commission_interne_id):
    obj = CommissionInterne.objects.filter(id_comission_interne=commission_interne_id).first()
    if not obj:
        raise NotFound("Commission interne not found")
    return obj


def get_commission_externe_or_404(commission_externe_id):
    obj = CommissionExterne.objects.filter(id_comission_externe=commission_externe_id).first()
    if not obj:
        raise NotFound("Commission externe not found")
    return obj


# ── Membre validation ───────────────────────────────────────────────


def _validate_membre_exists(membre_id):
    acteurs_url = settings.ACTEURS_SERVICE_URL
    if not acteurs_url:
        return
    url = f"{acteurs_url.rstrip('/')}/membres/{membre_id}"
    try:
        response = requests.get(url, timeout=settings.ACTEURS_SERVICE_TIMEOUT)
    except requests.RequestException:
        raise ValidationError({"id_membre": ["Unable to validate id_membre at this time"]})
    if response.status_code != 200:
        raise ValidationError({"id_membre": ["id_membre does not exist"]})


# ── Commission Evaluation: membres ──────────────────────────────────


def list_commission_eval_membres(commission_id):
    commission = get_commission_eval_or_404(commission_id)
    return MembresCommissionEvaluation.objects.filter(id_comission=commission).order_by("id_membre")


def add_membre_to_commission_eval(commission_id, membre_id):
    commission = get_commission_eval_or_404(commission_id)
    _validate_membre_exists(membre_id)
    MembresCommissionEvaluation.objects.get_or_create(id_comission=commission, id_membre=membre_id)
    bump_cache_version()


def remove_membre_from_commission_eval(commission_id, membre_id):
    commission = get_commission_eval_or_404(commission_id)
    deleted_count, _ = MembresCommissionEvaluation.objects.filter(
        id_comission=commission, id_membre=membre_id,
    ).delete()
    if deleted_count == 0:
        raise NotFound("Membre not linked to this commission")
    bump_cache_version()


# ── Commission Interne: membres ─────────────────────────────────────


def list_commission_interne_membres(commission_interne_id):
    commission = get_commission_interne_or_404(commission_interne_id)
    return MembresCommissionInterne.objects.filter(id_commision_interne=commission).order_by("id_membre")


def add_membre_to_commission_interne(commission_interne_id, membre_id):
    commission = get_commission_interne_or_404(commission_interne_id)
    _validate_membre_exists(membre_id)
    MembresCommissionInterne.objects.get_or_create(id_commision_interne=commission, id_membre=membre_id)
    bump_cache_version()


def remove_membre_from_commission_interne(commission_interne_id, membre_id):
    commission = get_commission_interne_or_404(commission_interne_id)
    deleted_count, _ = MembresCommissionInterne.objects.filter(
        id_commision_interne=commission, id_membre=membre_id,
    ).delete()
    if deleted_count == 0:
        raise NotFound("Membre not linked to this commission")
    bump_cache_version()


# ── Service commissions aggregation ──────────────────────────────────


def list_service_commissions(service_id):
    from .services_contractants import get_service_or_404

    service = get_service_or_404(service_id)
    return {
        "commissions_evaluation": list(
            CommissionEvaluation.objects.filter(id_service=service).order_by("id_comission").values(
                "id_comission", "nom_comission", "categorie",
            )
        ),
        "commissions_internes": list(
            CommissionInterne.objects.filter(id_service=service).order_by("id_comission_interne").values(
                "id_comission_interne", "nom_comission", "type_comission",
            )
        ),
    }
