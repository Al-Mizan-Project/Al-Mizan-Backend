from rest_framework.exceptions import NotFound, ValidationError
from django.db.models import Q

from appels_service.models import AppelOffres, AppelOffresSuivi, DocumentsAppel


# ── Valid statut transitions ──────────────────────────────────────────

_TRANSITIONS = {
    "publier": {
        "from": {"brouillon"},
        "to": "publie",
        "error": "Seul un appel en statut 'brouillon' peut être publié.",
    },
    "cloturer_depot": {
        "from": {"publie"},
        "to": "depot_cloture",
        "error": "Seul un appel 'publié' peut être clôturé.",
    },
    "ouvrir_plis": {
        "from": {"depot_cloture"},
        "to": "plis_ouverts",
        "error": "Les plis ne peuvent être ouverts que lorsque le dépôt est clôturé.",
    },
    "annuler": {
        "from": {"brouillon", "publie", "depot_cloture"},
        "to": "annule",
        "error": "Un appel déjà clôturé (plis ouverts) ne peut pas être annulé.",
    },
}


# ── Querysets ─────────────────────────────────────────────────────────


def appels_offres_queryset(statut=None, service_id=None, search=None):
    queryset = AppelOffres.objects.order_by("-created_at")
    if statut:
        queryset = queryset.filter(statut=statut)
    if service_id is not None:
        queryset = queryset.filter(id_service_contractant=service_id)
    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search)
            | Q(titre__icontains=search)
            | Q(description__icontains=search)
        )
    return queryset


def appels_by_service_queryset(service_id):
    return AppelOffres.objects.filter(id_service_contractant=service_id).order_by("-created_at")


# ── Lookups ───────────────────────────────────────────────────────────


def get_appel_or_404(appel_id):
    obj = AppelOffres.objects.filter(id_appel_offres=appel_id).first()
    if not obj:
        raise NotFound("Appel d'offres not found")
    return obj


# ── Workflow actions ──────────────────────────────────────────────────


def _apply_transition(appel_id, action_name):
    transition = _TRANSITIONS[action_name]
    appel = get_appel_or_404(appel_id)
    if appel.statut not in transition["from"]:
        raise ValidationError({"statut": [transition["error"]]})
    appel.statut = transition["to"]
    appel.save(update_fields=["statut", "updated_at"])
    return appel


def action_publier(appel_id):
    return _apply_transition(appel_id, "publier")


def action_cloturer_depot(appel_id):
    return _apply_transition(appel_id, "cloturer_depot")


def action_ouvrir_plis(appel_id):
    return _apply_transition(appel_id, "ouvrir_plis")


def action_annuler(appel_id):
    return _apply_transition(appel_id, "annuler")


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
