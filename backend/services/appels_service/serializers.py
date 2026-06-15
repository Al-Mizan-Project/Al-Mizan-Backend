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
            "reference",
            "titre",
            "description",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
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
            "validation_level",
            "commission_id",
            "validated_by",
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

    def validate_operateurs_invites(self, value):
        normalized = _normalize_operateurs_invites(value)
        for operateur_id in normalized:
            _validate_operateur_economique(operateur_id)
        return normalized

    def validate_id_service_contractant(self, value):
        return _validate_service_contractant(value)

    def validate_type_procedure(self, value):
        raw = (value or "").strip().lower()
        if raw in {"publique", "public"} or "ouvert" in raw:
            return "publique"
        if raw in {"restreint", "restreinte"} or "restreint" in raw:
            return "restreint"
        if raw in {"gre_a_gre", "gre a gre", "gré à gré"}:
            return "gre_a_gre"
        if raw == "consultation" or "consult" in raw:
            return "consultation"
        raise serializers.ValidationError("Unsupported type_procedure")

    def validate(self, attrs):
        attrs = super().validate(attrs)

        type_procedure = attrs.get(
            "type_procedure",
            getattr(self.instance, "type_procedure", "publique"),
        )
        operateurs_invites = attrs.get("operateurs_invites")
        requires_invites = type_procedure in {"restreint", "consultation", "gre_a_gre"}

        if requires_invites:
            if operateurs_invites is None:
                if self.instance is None:
                    raise serializers.ValidationError(
                        {"operateurs_invites": ["At least one invited operator is required for this procedure."]}
                    )
                existing_count = self.instance.operateurs_invites.count()
                if existing_count == 0:
                    raise serializers.ValidationError(
                        {"operateurs_invites": ["At least one invited operator is required for this procedure."]}
                    )
            elif len(operateurs_invites) == 0:
                raise serializers.ValidationError(
                    {"operateurs_invites": ["At least one invited operator is required for this procedure."]}
                )

        if type_procedure == "publique" and operateurs_invites:
            raise serializers.ValidationError(
                {"operateurs_invites": ["Invited operators can only be set for restricted, consultation or gre_a_gre procedures."]}
            )

        return attrs


class AppelOffresCreateSerializer(_AppelOffresWriteSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_appel_offres",
            "id_service_contractant",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
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
            "validation_level",
            "commission_id",
            "validated_by",
            "operateurs_invites",
            "statut",
            "etat_execution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_appel_offres", "etat_execution", "created_at", "updated_at"]

    def create(self, validated_data):
        operateurs_invites = validated_data.pop("operateurs_invites", [])
        appel = super().create(validated_data)
        if operateurs_invites:
            _sync_operateurs_invites(appel, operateurs_invites)
        return appel


class AppelOffresUpdateSerializer(_AppelOffresWriteSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_service_contractant",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
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
            "validation_level",
            "commission_id",
            "validated_by",
            "statut",
            "operateurs_invites",
        ]

    def update(self, instance, validated_data):
        operateurs_invites = validated_data.pop("operateurs_invites", None)
        appel = super().update(instance, validated_data)

        if appel.type_procedure == "publique":
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


# ── Documents Appel ───────────────────────────────────────────────────


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
