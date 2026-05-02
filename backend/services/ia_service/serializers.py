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


"""
Serializers pour le module d'aide à la rédaction du CDC.
À ajouter dans ia_service/serializers.py (ou fusionner avec le fichier existant).
"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# Serializers de réponse (sortie)
# ---------------------------------------------------------------------------

class AlerteCritiqueSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.ChoiceField(choices=[
        "terme_discriminant",
        "clause_restrictive",
        "critere_disproportionne",
        "donnee_manquante",
        "violation_loi",
    ])
    niveau = serializers.ChoiceField(choices=["critique", "attention", "info"])
    extrait = serializers.CharField()
    article_loi = serializers.CharField()
    message = serializers.CharField()
    suggestion = serializers.CharField()


class AnalyseSectionSerializer(serializers.Serializer):
    section = serializers.ChoiceField(choices=[
        "objet_marche",
        "specifications_techniques",
        "criteres_eligibilite",
        "criteres_evaluation",
        "conditions_execution",
        "clauses_administratives",
        "protection_donnees",
    ])
    statut = serializers.ChoiceField(choices=[
        "present_conforme",
        "present_attention",
        "present_non_conforme",
        "absent",
    ])
    commentaire = serializers.CharField()


class SuggestionAmeliorationSerializer(serializers.Serializer):
    priorite = serializers.ChoiceField(choices=["haute", "moyenne", "faible"])
    titre = serializers.CharField()
    description = serializers.CharField()


class PipelineMetaSerializer(serializers.Serializer):
    id_document = serializers.IntegerField()
    ocr_engine = serializers.CharField()
    char_count = serializers.IntegerField()
    ocr_used = serializers.BooleanField()


class AideRedactionResponseSerializer(serializers.Serializer):
    score_conformite = serializers.IntegerField(min_value=0, max_value=100)
    resume_general = serializers.CharField()
    alertes_critiques = AlerteCritiqueSerializer(many=True)
    analyse_sections = AnalyseSectionSerializer(many=True)
    suggestions_amelioration = SuggestionAmeliorationSerializer(many=True)
    needs_human_validation = serializers.BooleanField()
    _source = serializers.CharField(required=False)
    _pipeline = PipelineMetaSerializer(required=False)


# ---------------------------------------------------------------------------
# Serializers de requête (entrée)
# ---------------------------------------------------------------------------

class AideRedactionRequestSerializer(serializers.Serializer):
    # Contexte de l'appel (envoyé directement par le frontend/service appelant)
    type_procedure = serializers.CharField()
    type_prestation = serializers.CharField()
    montant_estime = serializers.FloatField(required=False, allow_null=True)
    wilaya = serializers.CharField(required=False, default="")
    poids_technique = serializers.IntegerField(default=50)
    poids_financier = serializers.IntegerField(default=50)
    qualification_category = serializers.CharField(required=False, default="")
    minimum_experience_years = serializers.IntegerField(default=0)
    minimum_revenue_da = serializers.IntegerField(default=0)
    participation_conditions = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    required_docs_admin = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    required_docs_tech = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    # Le document CDC en binaire
    fichier_cdc = serializers.FileField()
