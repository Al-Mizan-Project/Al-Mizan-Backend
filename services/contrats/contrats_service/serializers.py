import requests
from django.conf import settings
from rest_framework import serializers

from .models import Validation, Contrat, DocumentContrat


# ---------------------------------------------------------------------------
# Helper: validate a foreign key by calling another service
# ---------------------------------------------------------------------------

def _validate_remote_fk(value, service_url_setting, path_template, field_label):
    """
    Calls a remote microservice to check that a given ID exists.
    *service_url_setting* is the Django settings attribute name (e.g.
    "SOUMISSIONS_SERVICE_URL").  *path_template* is a format-string with a
    single ``{}`` placeholder for the ID.
    """
    base_url = getattr(settings, service_url_setting, "")
    if not base_url:
        return value  # skip validation when service URL not configured
    url = f"{base_url.rstrip('/')}/{path_template.format(value)}"
    timeout = getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        raise serializers.ValidationError(
            f"Unable to validate {field_label} at this time"
        )
    if response.status_code != 200:
        raise serializers.ValidationError(f"{field_label} does not exist")
    return value


# ---------------------------------------------------------------------------
# Validation serializers
# ---------------------------------------------------------------------------

class ValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Validation
        fields = [
            "id_validation",
            "id_organisation",
            "id_soumission",
            "type",
            "is_validated",
            "commentaire",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_validation", "created_at", "updated_at"]

    def validate_id_organisation(self, value):
        return _validate_remote_fk(
            value, "ACTEURS_SERVICE_URL", "organisations/{}", "id_organisation"
        )

    def validate_id_soumission(self, value):
        return _validate_remote_fk(
            value, "SOUMISSIONS_SERVICE_URL", "soumissions/{}", "id_soumission"
        )


class ValidationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Validation
        fields = [
            "id_organisation",
            "id_soumission",
            "type",
            "is_validated",
            "commentaire",
        ]

    def validate_id_organisation(self, value):
        return _validate_remote_fk(
            value, "ACTEURS_SERVICE_URL", "organisations/{}", "id_organisation"
        )

    def validate_id_soumission(self, value):
        return _validate_remote_fk(
            value, "SOUMISSIONS_SERVICE_URL", "soumissions/{}", "id_soumission"
        )


# ---------------------------------------------------------------------------
# Contrat serializers
# ---------------------------------------------------------------------------

class ContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        fields = [
            "id_contrat",
            "id_soumission",
            "id_service_contractants",
            "numero_contrat",
            "date_signature",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id_contrat", "created_at", "updated_at"]

    def validate_id_soumission(self, value):
        return _validate_remote_fk(
            value, "SOUMISSIONS_SERVICE_URL", "soumissions/{}", "id_soumission"
        )

    def validate_id_service_contractants(self, value):
        return _validate_remote_fk(
            value,
            "CONTRACTANT_SERVICE_URL",
            "services-contractants/{}",
            "id_service_contractants",
        )


class ContratUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        fields = [
            "id_soumission",
            "id_service_contractants",
            "numero_contrat",
            "date_signature",
            "statut",
        ]

    def validate_id_soumission(self, value):
        return _validate_remote_fk(
            value, "SOUMISSIONS_SERVICE_URL", "soumissions/{}", "id_soumission"
        )

    def validate_id_service_contractants(self, value):
        return _validate_remote_fk(
            value,
            "CONTRACTANT_SERVICE_URL",
            "services-contractants/{}",
            "id_service_contractants",
        )


# ---------------------------------------------------------------------------
# DocumentContrat serializer
# ---------------------------------------------------------------------------

class DocumentContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentContrat
        fields = ["id", "id_contrat", "id_document"]
        read_only_fields = ["id"]
