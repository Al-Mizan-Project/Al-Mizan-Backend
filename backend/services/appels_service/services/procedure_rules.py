from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import unicodedata

from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class ProcedureRules:
    requires_validation: bool
    requires_invites: bool
    requires_operateur_choisi: bool
    requires_doc_cdc: bool
    requires_doc_justification: bool
    requires_doc_besoin: bool
    force_null_timeline: bool
    allow_execution: bool


PROCEDURE_RULES = {
    "publique": ProcedureRules(
        requires_validation=True,
        requires_invites=False,
        requires_operateur_choisi=False,
        requires_doc_cdc=False,
        requires_doc_justification=False,
        requires_doc_besoin=False,
        force_null_timeline=False,
        allow_execution=True,
    ),
    "restreint": ProcedureRules(
        requires_validation=True,
        requires_invites=True,
        requires_operateur_choisi=False,
        requires_doc_cdc=True,
        requires_doc_justification=True,
        requires_doc_besoin=False,
        force_null_timeline=False,
        allow_execution=True,
    ),
    "gre_a_gre": ProcedureRules(
        requires_validation=True,
        requires_invites=False,
        requires_operateur_choisi=True,
        requires_doc_cdc=True,
        requires_doc_justification=True,
        requires_doc_besoin=False,
        force_null_timeline=True,
        allow_execution=False,
    ),
    "consultation": ProcedureRules(
        requires_validation=False,
        requires_invites=False,
        requires_operateur_choisi=True,
        requires_doc_cdc=False,
        requires_doc_justification=False,
        requires_doc_besoin=True,
        force_null_timeline=True,
        allow_execution=False,
    ),
}


_TYPE_ALIASES = {
    "publique": "publique",
    "public": "publique",
    "appel d offres ouvert": "publique",
    "appel d offres publique": "publique",
    "ao ouvert": "publique",
    "restreint": "restreint",
    "appel d offres restreint": "restreint",
    "ao restreint": "restreint",
    "gre a gre": "gre_a_gre",
    "gre a gre simple": "gre_a_gre",
    "consultation": "consultation",
    "interne": "publique",
}


def _slugify(value: str) -> str:
    raw = (value or "").strip().lower()
    raw = raw.replace("’", "'")
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.replace("-", " ").replace("_", " ").replace("'", " ")
    return " ".join(raw.split())


def normalize_type_procedure(value: str | None) -> str | None:
    if not value:
        return None
    slug = _slugify(value)
    return _TYPE_ALIASES.get(slug)


def get_procedure_rules(type_procedure: str | None) -> ProcedureRules:
    normalized = normalize_type_procedure(type_procedure)
    if not normalized:
        raise ValidationError({"type_procedure": ["Type de procedure invalide."]})
    return PROCEDURE_RULES[normalized]


def resolve_validation_routing(montant_estime, wilaya: str, secteur: str, service_id=None) -> tuple[str | None, str]:
    if montant_estime is None:
        raise ValidationError({"montant_estime": ["Le montant estime est obligatoire pour la validation."]})
    try:
        montant = Decimal(str(montant_estime))
    except (InvalidOperation, TypeError):
        raise ValidationError({"montant_estime": ["Montant estime invalide."]})
    if montant <= 0:
        raise ValidationError({"montant_estime": ["Le montant estime doit etre superieur a zero."]})

    from acteurs_service.models import CommissionExterne, NiveauCompetence

    # Threshold escalation: an AO routes to the highest external commission whose
    # seuil it exceeds (national > sectorielle > wilaya), otherwise to internal
    # validation. Levels that are not configured are skipped instead of failing,
    # so creation always succeeds and naturally falls back to internal review.
    national = (
        CommissionExterne.objects.filter(niveau_competence=NiveauCompetence.NATIONAL)
        .order_by("-seuil")
        .first()
    )
    if national and montant > national.seuil:
        return str(national.organisation_id), "externe_nationale"

    if secteur:
        sectorielle = (
            CommissionExterne.objects.filter(
                niveau_competence=NiveauCompetence.SECTORIELLE,
                organisation__secteur__iexact=secteur,
            )
            .order_by("-seuil")
            .first()
        )
        if sectorielle and montant > sectorielle.seuil:
            return str(sectorielle.organisation_id), "externe_secteur"

    if wilaya:
        wilaya_commission = (
            CommissionExterne.objects.filter(
                niveau_competence=NiveauCompetence.WILAYA,
                organisation__wilaya__iexact=wilaya,
            )
            .order_by("-seuil")
            .first()
        )
        if wilaya_commission and montant > wilaya_commission.seuil:
            return str(wilaya_commission.organisation_id), "externe_wilaya"

    return (str(service_id) if service_id is not None else None), "interne"
