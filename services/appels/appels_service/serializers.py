from django.conf import settings
from rest_framework import serializers
import requests

from .models import AppelOffres, DocumentsAppel


def _validate_service_contractant(value):
    contractant_url = getattr(settings, "CONTRACTANT_SERVICE_URL", "")
    if not contractant_url:
        return value
    url = f"{contractant_url.rstrip('/')}/services-contractants/{value}"
    try:
        response = requests.get(url, timeout=settings.CONTRACTANT_SERVICE_TIMEOUT)
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
        response = requests.get(url, timeout=settings.DOCUMENTS_SERVICE_TIMEOUT)
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_document at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_document does not exist")
    return value


# ── Appel Offres ─────────────────────────────────────────────────────


class AppelOffresSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_appel_offres",
            "id_service_contractant",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "montant_estime",
            "date_publication",
            "date_limite_soumission",
            "date_ouverture_plis",
            "poids_technique",
            "poids_financier",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_appel_offres", "created_at", "updated_at"]


class AppelOffresCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_appel_offres",
            "id_service_contractant",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "montant_estime",
            "date_publication",
            "date_limite_soumission",
            "date_ouverture_plis",
            "poids_technique",
            "poids_financier",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_appel_offres", "statut", "created_at", "updated_at"]

    def validate_id_service_contractant(self, value):
        return _validate_service_contractant(value)


class AppelOffresUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppelOffres
        fields = [
            "id_service_contractant",
            "reference",
            "titre",
            "description",
            "type_procedure",
            "montant_estime",
            "date_publication",
            "date_limite_soumission",
            "date_ouverture_plis",
            "poids_technique",
            "poids_financier",
        ]

    def validate_id_service_contractant(self, value):
        return _validate_service_contractant(value)


# ── Documents Appel ───────────────────────────────────────────────────


class DocumentsAppelSerializer(serializers.ModelSerializer):
    id_appel_offres = serializers.IntegerField(source="id_appel_offres_id", read_only=True)

    class Meta:
        model = DocumentsAppel
        fields = ["id", "id_document", "id_appel_offres"]
        read_only_fields = ["id", "id_appel_offres"]
