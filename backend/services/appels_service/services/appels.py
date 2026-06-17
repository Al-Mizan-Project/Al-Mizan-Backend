from rest_framework.exceptions import NotFound, ValidationError
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from appels_service.models import AppelOffres, AppelOffresSuivi, DocumentsAppel
from appels_service.services.procedure_rules import get_procedure_rules, resolve_validation_routing
from notifications_service.models import Notification


# ── Execution status transitions ─────────────────────────────────────

_EXECUTION_TRANSITIONS = {
    "publier": {
        "from": {"brouillon"},
        "to": "publie",
        "error": "Seul un appel en statut d'execution 'brouillon' peut etre publie.",
    },
    "cloturer_depot": {
        "from": {"publie"},
        "to": "depot_cloture",
        "error": "Seul un appel 'publie' peut etre cloture.",
    },
    "ouvrir_plis": {
        "from": {"depot_cloture"},
        "to": "plis_ouverts",
        "error": "Les plis ne peuvent etre ouverts que lorsque le depot est cloture.",
    },
    "annuler": {
        "from": {"brouillon", "publie", "depot_cloture"},
        "to": "annule",
        "error": "Un appel deja cloture (plis ouverts) ne peut pas etre annule.",
    },
}


# ── Querysets ─────────────────────────────────────────────────────────


def appels_offres_queryset(statut=None, service_id=None, search=None, request=None):
    queryset = AppelOffres.objects.prefetch_related("operateurs_invites", "suivis").order_by("-created_at")
    if statut:
        if isinstance(statut, str) and ',' in statut:
            statuts = [s.strip() for s in statut.split(',')]
            # Case-insensitive match using __iexact for each, combined with Q
            from django.db.models import Q
            q = Q()
            for s in statuts:
                q |= Q(statut__iexact=s)
            queryset = queryset.filter(q)
        else:
            queryset = queryset.filter(statut__iexact=statut)
    if service_id is not None:
        queryset = queryset.filter(id_service_contractant=service_id)
    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search)
            | Q(titre__icontains=search)
            | Q(description__icontains=search)
        )
    if request is not None:
        queryset = _filter_queryset_for_request(queryset, request)
    return queryset


def appels_by_service_queryset(service_id):
    return (
        AppelOffres.objects.prefetch_related("operateurs_invites")
        .filter(id_service_contractant=service_id)
        .order_by("-created_at")
    )


def _is_internal_request(request) -> bool:
    expected = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
    if not expected:
        return False
    provided = request.headers.get("X-Internal-Service-Token", "")
    return provided == expected


def _token_get(token, key):
    if token is None:
        return None
    getter = getattr(token, "get", None)
    if not getter:
        return None
    return getter(key)


def _get_role(request):
    token = getattr(request, "auth", None)
    role = _token_get(token, "role")
    if not role:
        role = getattr(getattr(request.user, "id_role", None), "nom_role", "")
    return str(role or "").strip().lower()


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_operator_id(request):
    token = getattr(request, "auth", None)
    for key in ("id_operateur_economique", "operateur_id", "operator_id"):
        raw = _token_get(token, key)
        if raw not in (None, ""):
            value = _coerce_int(raw)
            if value is not None:
                return value
    return None


def _get_commission_id(request):
    token = getattr(request, "auth", None)
    for key in ("commission_id", "id_commission", "organisation_id"):
        raw = _token_get(token, key)
        if raw not in (None, ""):
            return str(raw)

    membre_id = getattr(request.user, "id_membre", None)
    if not membre_id:
        return None

    try:
        from acteurs_service.models import Membre, TypeEntite
    except Exception:
        return None

    membre = (
        Membre.objects.select_related("organisation")
        .filter(id_membre=membre_id)
        .first()
    )
    if membre and membre.organisation and membre.organisation.type_entite == TypeEntite.COMMISSION_EXTERNE:
        return str(membre.organisation_id)
    return None


def _filter_queryset_for_request(queryset, request):
    if _is_internal_request(request):
        return queryset

    role = _get_role(request)
    if role == "operateur_economique":
        operateur_id = _get_operator_id(request)
        if operateur_id is None:
            return queryset.none()
        public_types = {
            "publique",
            "Appel d'offres ouvert",
            "Appel d'offres publique",
        }
        restricted = {
            "restreint",
            "gre_a_gre",
            "consultation",
            "Appel d'offres restreint",
            "Gré à gré",
            "Gre a gre",
            "Consultation",
        }
        return (
            queryset.filter(statut__iexact="valide")
            .filter(
                Q(type_procedure__in=public_types)
                | (
                    Q(type_procedure__in=restricted)
                    & (
                        Q(operateurs_invites__id_operateur_economique=operateur_id)
                        | Q(id_operateur_choisi=operateur_id)
                    )
                )
            )
            .distinct()
        )

    if role == "commission_externe":
        commission_id = _get_commission_id(request)
        if not commission_id:
            return queryset.none()
        return queryset.filter(statut__iexact="non_valide", commission_id=commission_id)

    return queryset


# ── Lookups ───────────────────────────────────────────────────────────


def get_appel_or_404(appel_id):
    obj = AppelOffres.objects.filter(id_appel_offres=appel_id).first()
    if not obj:
        raise NotFound("Appel d'offres not found")
    return obj


# ── Workflow actions ──────────────────────────────────────────────────


def _apply_transition(appel_id, action_name):
    transition = _EXECUTION_TRANSITIONS[action_name]
    appel = get_appel_or_404(appel_id)
    rules = get_procedure_rules(appel.type_procedure)
    if not rules.allow_execution:
        raise ValidationError({"type_procedure": ["Cette procedure ne permet pas d'execution."]})
    if appel.statut != "valide":
        raise ValidationError({"statut": ["L'appel doit etre valide avant execution."]})
    if appel.etat_execution not in transition["from"]:
        raise ValidationError({"etat_execution": [transition["error"]]})
    appel.etat_execution = transition["to"]
    update_fields = ["etat_execution", "updated_at"]
    if action_name == "publier" and not appel.date_publication:
        appel.date_publication = timezone.now()
        update_fields.append("date_publication")
    appel.save(update_fields=update_fields)
    return appel


def action_publier(appel_id):
    return _apply_transition(appel_id, "publier")


def action_cloturer_depot(appel_id):
    return _apply_transition(appel_id, "cloturer_depot")


def action_ouvrir_plis(appel_id):
    return _apply_transition(appel_id, "ouvrir_plis")


def action_annuler(appel_id):
    return _apply_transition(appel_id, "annuler")


def action_soumettre_validation(appel_id, validated_by=None):
    appel = get_appel_or_404(appel_id)
    rules = get_procedure_rules(appel.type_procedure)
    if not rules.requires_validation:
        raise ValidationError({"type_procedure": ["Cette procedure ne passe pas en validation."]})

    commission_id, validation_level = resolve_validation_routing(
        appel.montant_estime,
        appel.wilaya,
        appel.secteur,
    )
    appel.commission_id = commission_id
    appel.validation_level = validation_level
    appel.statut = "non_valide"
    appel.validated_by = str(validated_by) if validated_by else None
    appel.save(update_fields=["commission_id", "validation_level", "statut", "validated_by", "updated_at"])
    return appel


def action_valider(appel_id, validated_by):
    appel = get_appel_or_404(appel_id)
    rules = get_procedure_rules(appel.type_procedure)
    if not rules.requires_validation:
        raise ValidationError({"type_procedure": ["Cette procedure ne passe pas en validation."]})
    if str(appel.statut).lower() != "non_valide":
        raise ValidationError({"statut": ["Seuls les appels non valides peuvent etre valides."]})
    if not validated_by:
        raise ValidationError({"validated_by": ["Le membre validateur est obligatoire."]})
    appel.statut = "valide"
    appel.validated_by = str(validated_by)
    appel.save(update_fields=["statut", "validated_by", "updated_at"])
    return appel


def action_refuser(appel_id, validated_by):
    appel = get_appel_or_404(appel_id)
    rules = get_procedure_rules(appel.type_procedure)
    if not rules.requires_validation:
        raise ValidationError({"type_procedure": ["Cette procedure ne passe pas en validation."]})
    if str(appel.statut).lower() != "non_valide":
        raise ValidationError({"statut": ["Seuls les appels non valides peuvent etre refuses."]})
    if not validated_by:
        raise ValidationError({"validated_by": ["Le membre validateur est obligatoire."]})
    appel.statut = "refuse"
    appel.validated_by = str(validated_by)
    appel.save(update_fields=["statut", "validated_by", "updated_at"])
    return appel


# ── Documents ─────────────────────────────────────────────────────────


def list_appel_documents(appel_id):
    appel = get_appel_or_404(appel_id)
    return DocumentsAppel.objects.filter(id_appel_offres=appel).order_by("id_document")


def get_document_link_or_404(appel_id, document_id):
    link = DocumentsAppel.objects.filter(
        id_appel_offres__id_appel_offres=appel_id,
        id_document=document_id,
    ).first()
    if not link:
        raise NotFound("Document not linked to this appel")
    return link


def add_document_to_appel(appel_id, document_id):
    appel = get_appel_or_404(appel_id)
    DocumentsAppel.objects.get_or_create(
        id_appel_offres=appel,
        id_document=document_id,
    )


def remove_document_from_appel(appel_id, document_id):
    link = get_document_link_or_404(appel_id, document_id)
    link.delete()


# ── Suivis utilisateur ───────────────────────────────────────────────


def list_watched_appels_for_user(user_id):
    return AppelOffresSuivi.objects.filter(id_utilisateur=user_id).order_by("-created_at")


def is_appel_watched_by_user(appel_id, user_id):
    appel = get_appel_or_404(appel_id)
    return AppelOffresSuivi.objects.filter(id_appel_offres=appel, id_utilisateur=user_id).exists()


def watch_appel_for_user(appel_id, user_id):
    appel = get_appel_or_404(appel_id)
    return AppelOffresSuivi.objects.get_or_create(
        id_appel_offres=appel,
        id_utilisateur=user_id,
    )


def unwatch_appel_for_user(appel_id, user_id):
    appel = get_appel_or_404(appel_id)
    deleted, _ = AppelOffresSuivi.objects.filter(
        id_appel_offres=appel,
        id_utilisateur=user_id,
    ).delete()
    return deleted > 0


def affect_validator_to_appel(appel_id, validator_id):
    """
    Affecte un validateur à un appel d'offres, crée une entrée de suivi et notifie le validateur.
    
    Args:
        appel_id: ID de l'appel d'offres
        validator_id: ID de l'utilisateur validateur à affecter
    
    Returns:
        Le tuple (appel, suivi, notification)
    """
    if not validator_id:
        raise ValidationError({"validator_id": ["Le validateur est obligatoire."]})
    
    appel = get_appel_or_404(appel_id)
    
    # Mettre à jour le champ validated_by
    appel.validated_by = str(validator_id)
    appel.save(update_fields=["validated_by", "updated_at"])
    
    # Remplacer les suivis existants par un suivi pour le nouveau validateur
    # (suppression des anciens, puis création d'un nouveau pour remettre le compteur à zéro)
    AppelOffresSuivi.objects.filter(id_appel_offres=appel).delete()
    suivi = AppelOffresSuivi.objects.create(
        id_appel_offres=appel,
        id_utilisateur=int(validator_id),
    )

    # Créer une notification pour le validateur choisi
    notification = Notification.objects.create(
        utilisateur_id=int(validator_id),
        type_notification="AFFECTATION_VALIDATEUR",
        titre="Nouvelle affectation de validation",
        message=(
            f"Vous avez été affecté(e) comme validateur pour l'appel d'offres "
            f"{appel.reference or appel.id_appel_offres}."
        ),
        priorite="haute",
        categorie="appels",
        entite_liee_type="appel_offre",
        entite_liee_id=appel.id_appel_offres,
        statut="envoyée",
        sent_at=timezone.now(),
    )

    return appel, suivi, notification
