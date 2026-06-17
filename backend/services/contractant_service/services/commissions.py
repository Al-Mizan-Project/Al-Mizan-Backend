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
import re


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
    try:
        user_id = int(membre_id)
    except (TypeError, ValueError):
        raise ValidationError({"id_membre": ["id_membre must be an auth user id"]})

    from auth_service.models import Utilisateur

    if not Utilisateur.objects.filter(id_utilisateur=user_id).exists():
        raise ValidationError({"id_membre": ["id_membre does not exist"]})
    return user_id


# ── Commission Evaluation: membres ──────────────────────────────────


def list_commission_eval_membres(commission_id):
    commission = get_commission_eval_or_404(commission_id)
    return MembresCommissionEvaluation.objects.filter(id_comission=commission).order_by("id_membre")


def add_membre_to_commission_eval(commission_id, membre_id):
    commission = get_commission_eval_or_404(commission_id)
    user_id = _validate_membre_exists(membre_id)
    MembresCommissionEvaluation.objects.get_or_create(id_comission=commission, id_membre=user_id)
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
    user_id = _validate_membre_exists(membre_id)
    MembresCommissionInterne.objects.get_or_create(id_commision_interne=commission, id_membre=user_id)
    bump_cache_version()


def remove_membre_from_commission_interne(commission_interne_id, membre_id):
    commission = get_commission_interne_or_404(commission_interne_id)
    user_id = _validate_membre_exists(membre_id)
    deleted_count, _ = MembresCommissionInterne.objects.filter(
        id_commision_interne=commission, id_membre=user_id,
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

# ── Logic Determination Commission Externe Competente ───────────────

def convert_threshold(text):
    if not text: return 0
    # Extract all digits and join them (to handle spaces like 10 000 000)
    digits = "".join(re.findall(r'\d+', text))
    return int(digits) if digits else 0

def get_commission_externe_competente(appel_id):
    """
    Détermine la commission externe compétente pour un appel d'offres donné.
    Retourne l'objet CommissionExterne ou None si transmission directe à la tutelle.
    """
    from .services_contractants import get_service_or_404
    
    # 1. Récupérer l'appel d'offres via le service Appels
    appels_url = f"{settings.APPELS_SERVICE_URL.rstrip('/')}/appels-offres/{appel_id}"
    try:
        response = requests.get(
            appels_url,
            timeout=5,
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        )
        if response.status_code != 200:
            raise NotFound("Appel d'offres non trouvé")
        appel_data = response.json()
    except requests.RequestException:
        raise ValidationError("Service appels non joignable")

    montant_estime = float(appel_data.get("montant_estime") or 0)
    service_id = appel_data.get("id_service_contractant")
    
    # 2. Récupérer le service contractant et sa catégorie
    service = get_service_or_404(service_id)
    cat_sc = service.categorie.lower()
    
    # Mapping de normalisation entre ServiceContractant.categorie et CommissionExterne.niveau_competance
    mapping = {
        "communal": "Communale",
        "commune": "Communale",
        "wilaya": "de Wilaya",
        "ministériel": "Sectorielle",
        "ministeriel": "Sectorielle",
        "national": "Nationale"
    }
    
    target_niveau = mapping.get(cat_sc)
    if not target_niveau:
        return None

    # 3. Trouver la commission externe correspondante
    commissions = CommissionExterne.objects.filter(niveau_competance=target_niveau)
    
    for ce in commissions:
        seuil = convert_threshold(ce.seuils_competence_financiere)
        if montant_estime > seuil:
            return ce
            
    return None
