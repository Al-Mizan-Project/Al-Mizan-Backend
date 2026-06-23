"""
contrats_service/serializers.py

Serializers for the Attribution-based contract/validation workflow.
The Attribution model lives in soumissions_app.
"""

from rest_framework import serializers
from soumissions_app.models import Attribution


class AttributionSerializer(serializers.ModelSerializer):
    """Full read serializer — used for list and detail views."""

    soumission_id = serializers.SerializerMethodField()
    id_soumissionnaire = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    delayDays = serializers.SerializerMethodField()
    validationDeadline = serializers.SerializerMethodField()
    assignmentDate = serializers.SerializerMethodField()

    def get_soumission_id(self, obj):
        try:
            soumission = obj.soumission
            if soumission is not None:
                return soumission.id_soumission
        except Exception:
            pass
        return None

    def get_id_soumissionnaire(self, obj):
        try:
            soumission = obj.soumission
            if soumission is not None:
                return soumission.id_soumissionnaire
        except Exception:
            pass
        return None

    def get_assignmentDate(self, obj):
        base_date = obj.updated_at if obj.validated_by else obj.created_at
        return base_date.isoformat() if base_date else None

    def get_validationDeadline(self, obj):
        from datetime import timedelta
        base_date = obj.updated_at if obj.validated_by else obj.created_at
        if base_date:
            return (base_date + timedelta(days=7)).isoformat()
        return None

    def get_status(self, obj):
        from django.utils import timezone
        from datetime import timedelta

        statut_str = str(obj.statut).lower()
        if statut_str not in ["provisoire", "non_valide"]:
            return obj.statut

        base_date = obj.updated_at if obj.validated_by else obj.created_at
        if base_date:
            deadline = base_date + timedelta(days=7)
            if timezone.now() > deadline:
                return "En Retard"
        return "En Cours"

    def get_delayDays(self, obj):
        from django.utils import timezone
        from datetime import timedelta

        statut_str = str(obj.statut).lower()
        if statut_str not in ["provisoire", "non_valide"]:
            return None

        base_date = obj.updated_at if obj.validated_by else obj.created_at
        if base_date:
            deadline = base_date + timedelta(days=7)
            now = timezone.now()
            if now > deadline:
                return (now - deadline).days
        return None

    class Meta:
        model = Attribution
        fields = [
            "id",
            "service_contractant_id",
            "soumission_id",
            "id_soumissionnaire",
            "appel_id",
            "commission_id",
            "validated_by",
            "validation_level",
            "statut",
            "created_at",
            "updated_at",
            "status",
            "delayDays",
            "validationDeadline",
            "assignmentDate",
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
