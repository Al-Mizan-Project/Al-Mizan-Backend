from rest_framework import serializers

from .models import DetectionAnomalieIA


class DetectionAnomalieIASerializer(serializers.ModelSerializer):
    class Meta:
        model = DetectionAnomalieIA
        fields = "__all__"


class DetecterAnomaliesInputSerializer(serializers.Serializer):
    """Input for manual anomaly detection with soumission data provided."""
    id_appel_offre = serializers.IntegerField()
    soumissions = serializers.ListField(child=serializers.DictField(), required=False)
    montant_estime = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False,
        help_text="Estimated budget for relative anomaly scoring",
    )
    historical_wins = serializers.ListField(
        child=serializers.DictField(), required=False,
        help_text="Historical winning data for bid rotation detection",
    )


class DetecterAnomaliesAutoInputSerializer(serializers.Serializer):
    """
    Input for automatic anomaly detection. 
    The IA service will fetch soumission data from the soumissions service.
    """
    id_appel_offre = serializers.IntegerField()
    montant_estime = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False,
    )


class DetecterSaucissonnageInputSerializer(serializers.Serializer):
    """Input for saucissonnage (market splitting) detection."""
    appels = serializers.ListField(
        child=serializers.DictField(),
        help_text=(
            "List of appel d'offres data to analyze. Each dict should include: "
            "id_appel_offre, id_service_contractant, titre, description, "
            "montant_estime, date_publication, type_procedure"
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
    required_documents = serializers.ListField(child=serializers.CharField(max_length=100), required=False)
    provided_documents = serializers.ListField(child=serializers.DictField(), required=False)


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


class AnomalySummarySerializer(serializers.Serializer):
    """Read-only serializer for anomaly analysis summaries."""
    total_anomalies = serializers.IntegerField()
    soumissions_analysees = serializers.IntegerField(required=False)
    soumissions_affectees = serializers.IntegerField(required=False)
    appels_analyses = serializers.IntegerField(required=False)
    appels_affectes = serializers.IntegerField(required=False)
    repartition_par_type = serializers.DictField()
    repartition_par_severite = serializers.DictField()
    score_risque_global = serializers.IntegerField(required=False)
    score_risque_saucissonnage = serializers.IntegerField(required=False)
    niveau_risque = serializers.CharField()
    recommandation = serializers.CharField()