from rest_framework import serializers

from .models import DetectionAnomalieIA


class DetectionAnomalieIASerializer(serializers.ModelSerializer):
    """Full model serializer — used internally; API responses use custom shapes."""

    id_anomalie_ia = serializers.IntegerField(
        source="id_detection_anomalie_ia", read_only=True
    )

    class Meta:
        model = DetectionAnomalieIA
        fields = [
            "id_anomalie_ia",
            "id_soumission",
            "id_appel_offre",
            "type_anomalie",
            "niveau_severite",
            "score_confiance",
            "details",
            "statut_examen",
            "date_detection",
            "commentaire_examen",
            "date_examen",
            "soumissions_impliquees",
            "appels_impliques",
        ]


# ---------------------------------------------------------------------------
# Input serializers — anomaly detection
# ---------------------------------------------------------------------------
class DetecterAnomaliesInputSerializer(serializers.Serializer):
    """
    POST /ia/anomalies/detecter
    { "id_soumission": 45, "id_appel_offre": 10 }
    The view fetches full soumission + appel data from internal services.
    """
    id_soumission = serializers.IntegerField()
    id_appel_offre = serializers.IntegerField()


class DetecterAnomaliesAutoInputSerializer(serializers.Serializer):
    """
    POST /ia/anomalies/detecter-auto
    { "id_appel_offre": 10 }
    The view fetches all soumissions + appel data automatically.
    """
    id_appel_offre = serializers.IntegerField()



class DetecterSaucissonnageInputSerializer(serializers.Serializer):
    """Input for saucissonnage (market splitting) detection."""
    appels = serializers.ListField(
        child=serializers.DictField(),
        help_text=(
            "List of appel d'offres data to analyze. Each dict should include: "
            "id_appel_offre, id_service_contractant, titre, description, "
            "montant_estime, date_publication, type_procedure, "
            "and may include type_prestation, visibilite, wilaya/localisation"
        ),
    )
    id_service_contractant = serializers.IntegerField(
        required=False,
        help_text="Optional: filter analysis to a specific service contractant",
    )


class DetecterSaucissonnageAutoInputSerializer(serializers.Serializer):
    """
    Input for automatic saucissonnage detection. 
    The service will fetch appel d'offres data from the appels service.
    """
    id_service_contractant = serializers.IntegerField(
        help_text="Service contractant ID to analyze",
    )
    date_debut = serializers.DateField(
        required=False,
        help_text="Analysis start date (default: 1 year ago)",
    )
    date_fin = serializers.DateField(
        required=False,
        help_text="Analysis end date (default: today)",
    )


class StatutExamenPatchSerializer(serializers.Serializer):
    statut_examen = serializers.ChoiceField(
        choices=DetectionAnomalieIA.StatutExamen.choices,
    )
    commentaire_examen = serializers.CharField(
        max_length=2000, required=False, default="",
    )


class VerifierConformiteInputSerializer(serializers.Serializer):
    required_documents = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False
    )
    provided_documents = serializers.ListField(
        child=serializers.DictField(), required=False
    )


class VerifierConformiteAutomatiqueInputSerializer(serializers.Serializer):
    id_appel_offre = serializers.IntegerField()
    provided_document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    required_document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
    )
    required_documents = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
    )
    enforce_validity_checks = serializers.BooleanField(default=True)
    perform_ocr = serializers.BooleanField(default=True)


class CdcRedigerInputSerializer(serializers.Serializer):
    besoin = serializers.CharField(max_length=5000)
    type_procedure = serializers.CharField(max_length=100)
    contraintes = serializers.ListField(child=serializers.CharField(max_length=1000), required=False)


class CdcReviserInputSerializer(serializers.Serializer):
    texte = serializers.CharField(max_length=20000)