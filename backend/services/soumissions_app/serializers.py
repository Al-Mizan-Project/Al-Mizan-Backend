import json
from rest_framework import serializers
from .models import Soumission, SoumissionStatut


class SoumissionListSerializer(serializers.ModelSerializer):
    conformite_rapport = serializers.SerializerMethodField()

    class Meta:
        model = Soumission
        fields = [
            "id_soumission",
            "id_appel_offre",
            "id_soumissionnaire",
            "offre_financiere_chiffree_url",
            "document_ids",
            "statut",
            "montant_financier",
            "date_soumission",
            "conformite_statut",
            "conformite_rapport",
        ]

    def get_conformite_rapport(self, obj):
        rapport = obj.conformite_rapport
        if isinstance(rapport, str) and rapport:
            try:
                return json.loads(rapport)
            except Exception:
                pass
        return rapport


class SoumissionCreateSerializer(serializers.Serializer):
    id_appel_offre = serializers.IntegerField()
    id_soumissionnaire = serializers.IntegerField()
    offre_financiere_chiffree_url = serializers.URLField(max_length=500)
    cle_dechiffrement_hash = serializers.CharField()
    document_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class EvaluationCreateSerializer(serializers.Serializer):
    id_comission = serializers.IntegerField()
    id_utilisateur = serializers.IntegerField()
    type = serializers.ChoiceField(
        choices=["administrative", "technique", "financière"]
    )
    note = serializers.IntegerField(min_value=0, max_value=100)
    commentaire = serializers.CharField(required=False, default="", allow_blank=True)
