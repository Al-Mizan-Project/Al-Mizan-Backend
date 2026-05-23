from django.conf import settings
from rest_framework import serializers
import requests
from shared.permissions import internal_service_headers

from .models import (
    AchatSimple,
    AppelOffres,
    AppelOffresOperateurInvite,
    AppelOffresSuivi,
    DocumentsAppel,
)
from .services.procedure_rules import (
    get_procedure_rules,
    normalize_type_procedure,
    resolve_validation_routing,
)

# ── Fonctions de validation Microservices ────────────────────────────


def _validate_service_contractant(value):
    contractant_url = getattr(settings, "CONTRACTANT_SERVICE_URL", "")
    if not contractant_url:
        return value
    url = f"{contractant_url.rstrip('/')}/services-contractants/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.CONTRACTANT_SERVICE_TIMEOUT,
            headers=internal_service_headers(),
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_service_contractant at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_service_contractant does not exist")
    return value


def _validate_document(value):
    documents_url = getattr(settings, "DOCUMENTS_SERVICE_URL", "")
    if not documents_url:
        return value
    url = f"{documents_url.rstrip('/')}/documents/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.DOCUMENTS_SERVICE_TIMEOUT,
            headers=internal_service_headers(),
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_document at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_document does not exist")
    return value


def _validate_operateur_economique(value):
    acteurs_url = getattr(settings, "ACTEURS_SERVICE_URL", "")
    if not acteurs_url:
        return value
    url = f"{acteurs_url.rstrip('/')}/operateurs-economiques/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.ACTEURS_SERVICE_TIMEOUT,
            headers=internal_service_headers(),
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_operateur_economique at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_operateur_economique does not exist")
    return value


def _validate_commission(value):
    if value in (None, ""):
        return None
    acteurs_url = getattr(settings, "ACTEURS_SERVICE_URL", "")
    if not acteurs_url:
        return value
    url = f"{acteurs_url.rstrip('/')}/commissions/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.ACTEURS_SERVICE_TIMEOUT,
            headers=internal_service_headers(),
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate commission_id at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("commission_id does not exist")
    return value


def _validate_membre_commission(value):
    if value is None:
        return value
    acteurs_url = getattr(settings, "ACTEURS_SERVICE_URL", "")
    if not acteurs_url:
        return value
    url = f"{acteurs_url.rstrip('/')}/membres/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.ACTEURS_SERVICE_TIMEOUT,
            headers=internal_service_headers(),
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate validated_by (id_membre) at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("validated_by (id_membre) does not exist")
    return value


def _normalize_operateurs_invites(raw_ids):
    ordered_unique = []
    seen = set()
    for operateur_id in raw_ids:
        if operateur_id in seen:
            continue
        seen.add(operateur_id)
        ordered_unique.append(operateur_id)
    return ordered_unique


def _sync_operateurs_invites(appel, operateur_ids):
    target_ids = set(operateur_ids)
    existing = {
        item.id_operateur_economique: item
        for item in AppelOffresOperateurInvite.objects.filter(id_appel_offres=appel)
    }

    to_create = [
        AppelOffresOperateurInvite(
            id_appel_offres=appel,
            id_operateur_economique=operateur_id,
        )
        for operateur_id in target_ids
        if operateur_id not in existing
    ]
    if to_create:
        AppelOffresOperateurInvite.objects.bulk_create(to_create)

    to_delete = [
        item.id
        for operateur_id, item in existing.items()
        if operateur_id not in target_ids
    ]
    if to_delete:
        AppelOffresOperateurInvite.objects.filter(id__in=to_delete).delete()


# ── Appel Offres ─────────────────────────────────────────────────────


class AppelOffresOperateurInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppelOffresOperateurInvite
        fields = [
            "id",
            "id_operateur_economique",
            "statut_invitation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AppelOffresSerializer(serializers.ModelSerializer):
    operateurs_invites = AppelOffresOperateurInviteSerializer(many=True, read_only=True)
    location = serializers.CharField(source="localisation", read_only=True)

    class Meta:
        model = AppelOffres
        fields = [
            "id_appel_offres",
            "id_service_contractant",
            "commission_id",
            "validated_by",
            "validation_level",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
            "secteur",
            "localisation",
            "location",
            "montant_estime",
            "date_publication",
            "date_limite_soumission",
            "date_ouverture_plis",
            "poids_technique",
            "poids_financier",
            "required_docs_admin",
            "required_docs_tech",
            "required_docs_fin",
            "minimum_revenue_da",
            "qualification_category",
            "minimum_experience_years",
            "participation_conditions",
            "id_operateur_choisi",
            "id_doc_cdc",
            "id_doc_justification",
            "id_doc_besoin",
            "operateurs_invites",
            "statut",
            "etat_execution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_appel_offres", "created_at", "updated_at"]


class _AppelOffresWriteSerializer(serializers.ModelSerializer):
    type_procedure = serializers.CharField()
    operateurs_invites = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    location = serializers.CharField(source="localisation", required=False, allow_blank=True)

    def validate_commission_id(self, value):
        return _validate_commission(value)

    def validate_validated_by(self, value):
        return _validate_membre_commission(value)

    def validate_operateurs_invites(self, value):
        normalized = _normalize_operateurs_invites(value)
        for operateur_id in normalized:
            _validate_operateur_economique(operateur_id)
        return normalized

    def validate_id_operateur_choisi(self, value):
        if value in (None, ""):
            return None
        return _validate_operateur_economique(value)

    def validate_id_doc_cdc(self, value):
        if value in (None, ""):
            return None
        return _validate_document(value)

    def validate_id_doc_justification(self, value):
        if value in (None, ""):
            return None
        return _validate_document(value)

    def validate_id_doc_besoin(self, value):
        if value in (None, ""):
            return None
        return _validate_document(value)

    def validate_id_service_contractant(self, value):
        return _validate_service_contractant(value)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        type_procedure = attrs.get(
            "type_procedure",
            getattr(self.instance, "type_procedure", None),
        )
        normalized = normalize_type_procedure(type_procedure)
        if not normalized:
            raise serializers.ValidationError({"type_procedure": ["Type de procedure invalide."]})
        attrs["type_procedure"] = normalized

        rules = get_procedure_rules(normalized)
        operateurs_invites = attrs.get("operateurs_invites")
        id_operateur_choisi = attrs.get(
            "id_operateur_choisi",
            getattr(self.instance, "id_operateur_choisi", None),
        )
        id_doc_cdc = attrs.get("id_doc_cdc", getattr(self.instance, "id_doc_cdc", None))
        id_doc_justification = attrs.get(
            "id_doc_justification",
            getattr(self.instance, "id_doc_justification", None),
        )
        id_doc_besoin = attrs.get("id_doc_besoin", getattr(self.instance, "id_doc_besoin", None))

        errors = {}

        if rules.requires_invites:
            if operateurs_invites is None:
                if self.instance is None:
                    errors["operateurs_invites"] = [
                        "Au moins un operateur invite est requis pour cette procedure."
                    ]
                else:
                    if self.instance.operateurs_invites.count() == 0:
                        errors["operateurs_invites"] = [
                            "Au moins un operateur invite est requis pour cette procedure."
                        ]
            elif len(operateurs_invites) == 0:
                errors["operateurs_invites"] = [
                    "Au moins un operateur invite est requis pour cette procedure."
                ]
        else:
            if operateurs_invites:
                errors["operateurs_invites"] = [
                    "Les operateurs invites ne sont pas autorises pour cette procedure."
                ]

        if rules.requires_operateur_choisi:
            if not id_operateur_choisi:
                errors["id_operateur_choisi"] = [
                    "Un operateur choisi est requis pour cette procedure."
                ]
        else:
            if id_operateur_choisi:
                errors["id_operateur_choisi"] = [
                    "Un operateur choisi n'est pas autorise pour cette procedure."
                ]

        if rules.requires_doc_cdc and not id_doc_cdc:
            errors["id_doc_cdc"] = ["Le CDC est obligatoire pour cette procedure."]

        if rules.requires_doc_justification and not id_doc_justification:
            errors["id_doc_justification"] = [
                "Le document de justification est obligatoire pour cette procedure."
            ]

        if rules.requires_doc_besoin and not id_doc_besoin:
            errors["id_doc_besoin"] = [
                "Le document de besoin est obligatoire pour cette procedure."
            ]

        if errors:
            raise serializers.ValidationError(errors)

        if rules.force_null_timeline:
            attrs["date_limite_soumission"] = None
            attrs["date_ouverture_plis"] = None
            attrs["poids_technique"] = None
            attrs["poids_financier"] = None

        return attrs

    def _apply_validation_defaults(self, validated_data, rules, instance=None):
        if rules.requires_validation:
            current_statut = getattr(instance, "statut", "non_valide") if instance else "non_valide"
            if instance is None or current_statut == "non_valide":
                montant_estime = validated_data.get(
                    "montant_estime",
                    getattr(instance, "montant_estime", None),
                )
                wilaya = validated_data.get("wilaya", getattr(instance, "wilaya", ""))
                secteur = validated_data.get("secteur", getattr(instance, "secteur", ""))
                commission_id, validation_level = resolve_validation_routing(
                    montant_estime,
                    wilaya,
                    secteur,
                )
                validated_data["commission_id"] = commission_id
                validated_data["validation_level"] = validation_level
                validated_data["statut"] = "non_valide"
                validated_data["validated_by"] = None
        else:
            validated_data["commission_id"] = None
            validated_data["validation_level"] = "aucun"
            validated_data["statut"] = "valide"
            validated_data["validated_by"] = None

        return validated_data


class AppelOffresCreateSerializer(_AppelOffresWriteSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_appel_offres",
            "id_service_contractant",
            "commission_id",
            "validated_by",
            "validation_level",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
            "secteur",
            "localisation",
            "location",
            "montant_estime",
            "date_publication",
            "date_limite_soumission",
            "date_ouverture_plis",
            "poids_technique",
            "poids_financier",
            "required_docs_admin",
            "required_docs_tech",
            "required_docs_fin",
            "minimum_revenue_da",
            "qualification_category",
            "minimum_experience_years",
            "participation_conditions",
            "id_operateur_choisi",
            "id_doc_cdc",
            "id_doc_justification",
            "id_doc_besoin",
            "operateurs_invites",
            "statut",
            "etat_execution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id_appel_offres",
            "commission_id",
            "validated_by",
            "validation_level",
            "statut",
            "etat_execution",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        operateurs_invites = validated_data.pop("operateurs_invites", [])
        rules = get_procedure_rules(validated_data.get("type_procedure"))
        validated_data = self._apply_validation_defaults(validated_data, rules, instance=None)
        appel = super().create(validated_data)
        if operateurs_invites:
            _sync_operateurs_invites(appel, operateurs_invites)
        return appel


class AppelOffresUpdateSerializer(_AppelOffresWriteSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_service_contractant",
            "commission_id",
            "validated_by",
            "validation_level",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
            "secteur",
            "localisation",
            "location",
            "montant_estime",
            "date_publication",
            "date_limite_soumission",
            "date_ouverture_plis",
            "poids_technique",
            "poids_financier",
            "required_docs_admin",
            "required_docs_tech",
            "required_docs_fin",
            "minimum_revenue_da",
            "qualification_category",
            "minimum_experience_years",
            "participation_conditions",
            "id_operateur_choisi",
            "id_doc_cdc",
            "id_doc_justification",
            "id_doc_besoin",
            "operateurs_invites",
            "statut",
            "etat_execution",
        ]
        read_only_fields = [
            "commission_id",
            "validated_by",
            "validation_level",
            "statut",
            "etat_execution",
        ]

    def update(self, instance, validated_data):
        operateurs_invites = validated_data.pop("operateurs_invites", None)
        rules = get_procedure_rules(validated_data.get("type_procedure", instance.type_procedure))
        validated_data = self._apply_validation_defaults(validated_data, rules, instance=instance)
        appel = super().update(instance, validated_data)

        if not rules.requires_invites:
            AppelOffresOperateurInvite.objects.filter(id_appel_offres=appel).delete()
        elif operateurs_invites is not None:
            _sync_operateurs_invites(appel, operateurs_invites)

        return appel


# ── Achats Simples ────────────────────────────────────────────────────


class AchatSimpleSerializer(serializers.ModelSerializer):
    location = serializers.CharField(source="localisation", read_only=True)

    class Meta:
        model = AchatSimple
        fields = [
            "id_achat_simple",
            "id_service_contractant",
            "reference",
            "objet",
            "description",
            "type_prestation",
            "wilaya",
            "localisation",
            "location",
            "montant_estime",
            "id_operateur_economique",
            "date_demande",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_achat_simple", "created_at", "updated_at"]


class AchatSimpleCreateSerializer(serializers.ModelSerializer):
    location = serializers.CharField(source="localisation", required=False, allow_blank=True)

    class Meta:
        model = AchatSimple
        fields = [
            "id_achat_simple",
            "id_service_contractant",
            "reference",
            "objet",
            "description",
            "type_prestation",
            "wilaya",
            "localisation",
            "location",
            "montant_estime",
            "id_operateur_economique",
            "date_demande",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_achat_simple", "statut", "created_at", "updated_at"]

    def validate_id_service_contractant(self, value):
        return _validate_service_contractant(value)

    def validate_id_operateur_economique(self, value):
        if value is None:
            return value
        return _validate_operateur_economique(value)


class AchatSimpleUpdateSerializer(serializers.ModelSerializer):
    location = serializers.CharField(source="localisation", required=False, allow_blank=True)

    class Meta:
        model = AchatSimple
        fields = [
            "id_service_contractant",
            "reference",
            "objet",
            "description",
            "type_prestation",
            "wilaya",
            "localisation",
            "location",
            "montant_estime",
            "id_operateur_economique",
            "date_demande",
            "statut",
        ]

    def validate_id_service_contractant(self, value):
        return _validate_service_contractant(value)

    def validate_id_operateur_economique(self, value):
        if value is None:
            return value
        return _validate_operateur_economique(value)


# ── Documents Appel et Suivis ─────────────────────────────────────────


class DocumentsAppelSerializer(serializers.ModelSerializer):
    id_appel_offres = serializers.IntegerField(source="id_appel_offres_id", read_only=True)

    class Meta:
        model = DocumentsAppel
        fields = ["id", "id_document", "id_appel_offres"]
        read_only_fields = ["id", "id_appel_offres"]


class AppelOffresSuiviSerializer(serializers.ModelSerializer):
    id_appel_offres = serializers.IntegerField(source="id_appel_offres_id", read_only=True)

    class Meta:
        model = AppelOffresSuivi
        fields = ["id", "id_appel_offres", "id_utilisateur", "created_at"]
        read_only_fields = ["id", "created_at"]