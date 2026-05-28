"""
contrats_service/serializers.py

Serializers for the Attribution-based contract/validation workflow.
The Attribution model lives in soumissions_app.
"""

from rest_framework import serializers
from soumissions_app.models import Attribution


class AttributionSerializer(serializers.ModelSerializer):
    """Full read serializer — used for list and detail views."""

    soumission_id = serializers.IntegerField(source="soumission.id_soumission", read_only=True)

    class Meta:
        model = Attribution
        fields = [
            "id",
            "service_contractant_id",
            "soumission_id",
            "appel_id",
            "commission_id",
            "validated_by",
            "validation_level",
            "statut",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AttributionAffecterSerializer(serializers.Serializer):
    """Body for POST /validations/{id}/affecter — assign a member to validate."""

    validated_by = serializers.IntegerField(
        help_text="id_utilisateur du membre de commission affecté à la validation"
    )


class AttributionValiderSerializer(serializers.Serializer):

    # No extra fields needed — just calling the endpoint sets statut=definitive.
    # Optional comment can be added later.
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")
