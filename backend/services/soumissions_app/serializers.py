import json
from rest_framework import serializers
from .models import Soumission, SoumissionStatut

# ── AO metadata (mirrors seed_data.py) ──────────────────────────────────────
# In production these would come from the Appels service; for dev we keep a
# small lookup so the mobile app gets human-readable AO titles.
_AO_META = {
    1: ("AO-2026-001", "Construction d'un complexe scolaire — Alger"),
    2: ("AO-2026-002", "Réhabilitation de la route nationale RN5 — Blida"),
    3: ("AO-2026-003", "Équipement laboratoire universitaire — Oran"),
    4: ("AO-2026-004", "Fourniture mobilier de bureau — Direction régionale Sétif"),
    5: ("AO-2026-005", "Modernisation réseau fibre optique — Constantine"),
    6: ("AO-2026-006", "Acquisition de matériel informatique — DGSN"),
    7: ("AO-2026-007", "Aménagement espaces verts — Annaba"),
}

# ── Progression by statut ───────────────────────────────────────────────────
_PROGRESSION = {
    SoumissionStatut.SOUMIS:          16,
    SoumissionStatut.EN_OUVERTURE:    40,
    SoumissionStatut.EN_EVALUATION:   66,
    SoumissionStatut.EVALU_TERMINEE:  84,
    SoumissionStatut.ATTRIBUE:        100,
    SoumissionStatut.NON_RETENU:      100,
    SoumissionStatut.INFRUCTUEUX:     100,
    SoumissionStatut.RETRAITE:        0,
}


class SoumissionListSerializer(serializers.ModelSerializer):
    conformite_rapport = serializers.SerializerMethodField()
    rapport = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    reference_ao = serializers.SerializerMethodField()
    titre_ao = serializers.SerializerMethodField()
    progression = serializers.SerializerMethodField()
    nom_operateur = serializers.SerializerMethodField()

    class Meta:
        model = Soumission
        fields = [
            "id_soumission",
            "reference",
            "id_appel_offre",
            "id_soumissionnaire",
            "nom_operateur",
            "offre_financiere_chiffree_url",
            "document_ids",
            "statut",
            "montant_financier",
            "date_soumission",
            "conformite_statut",
            "conformite_rapport",
            "reference_ao",
            "titre_ao",
            "progression",
            "rapport",
        ]

    def get_nom_operateur(self, obj):
        try:
            from auth_service.models import Utilisateur
            from acteurs_service.models import Membre
            user = Utilisateur.objects.filter(id_utilisateur=obj.id_soumissionnaire).first()
            if user and user.id_membre:
                membre = Membre.objects.select_related('organisation').filter(id_membre=user.id_membre).first()
                if membre and membre.organisation:
                    return membre.organisation.nom_officiel
        except Exception:
            pass
        return None

    def get_reference(self, obj):
        year = obj.date_soumission.year
        return f"SOUM-{year}-{obj.id_appel_offre:02d}-{obj.id_soumission:04d}"

    def _parse_rapport(self, obj):
        rapport = obj.conformite_rapport
        if isinstance(rapport, str) and rapport:
            try:
                return json.loads(rapport)
            except Exception:
                pass
        return rapport

    def get_conformite_rapport(self, obj):
        return self._parse_rapport(obj)

    def get_rapport(self, obj):
        return self._parse_rapport(obj)

    def get_reference_ao(self, obj):
        meta = _AO_META.get(obj.id_appel_offre)
        return meta[0] if meta else f"AO-{obj.id_appel_offre:04d}"

    def get_titre_ao(self, obj):
        meta = _AO_META.get(obj.id_appel_offre)
        return meta[1] if meta else f"Appel d'offres N°{obj.id_appel_offre}"

    def get_progression(self, obj):
        return _PROGRESSION.get(obj.statut, 0)


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



class AffectationSerializer(serializers.Serializer):
    evaluateur_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    type_evaluation = serializers.ChoiceField(choices=['technique', 'administrative'])
