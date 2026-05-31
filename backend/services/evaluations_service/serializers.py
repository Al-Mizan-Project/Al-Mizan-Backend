from rest_framework import serializers
from .models import (
    ComissionEvaluation, MembresCommissionEvaluation, Evaluation,
    RegistreReception, RegistreIntegriteConfirmation,
    SeanceOuverture, PliOuverture, ParapheMembre,
    ConformiteOffer, CapacitesOffer, AssignationCT ,RapportCT ,
    EvalTechniqueOffer, EvalFinanciereOffer,
    ClassementEntry, ProcesVerbal, SignaturePV, SCDecision,
)


class MembresCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembresCommissionEvaluation
        fields = ['id', 'id_comission', 'id_utilisateur', 'role_label']


class ComissionEvaluationSerializer(serializers.ModelSerializer):
    membres = MembresCommissionSerializer(many=True, read_only=True)

    class Meta:
        model = ComissionEvaluation
        fields = ['id_comission', 'id_service', 'nom_comission', 'categorie', 'membres']


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = '__all__'


# ── Step 1 ────────────────────────────────────────────────────────────────────

class RegistreReceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistreReception
        fields = '__all__'


class ConfirmerIntegriteSerializer(serializers.Serializer):
    confirmed_by = serializers.IntegerField()


# ── Step 2 ────────────────────────────────────────────────────────────────────

class SeanceOuvertureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeanceOuverture
        fields = '__all__'


class OuvrirPliSerializer(serializers.Serializer):
    id_soumission = serializers.IntegerField()
    montant_declare = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)


class ParapheSerializer(serializers.Serializer):
    id_utilisateur = serializers.IntegerField()


# ── Step 3 ────────────────────────────────────────────────────────────────────

class ConformiteOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConformiteOffer
        fields = '__all__'


class DemandeComplementSerializer(serializers.Serializer):
    id_soumission = serializers.IntegerField()
    motif = serializers.CharField()


# ── Step 4 ────────────────────────────────────────────────────────────────────

class CapacitesOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacitesOffer
        fields = '__all__'


# ── Step 5 ────────────────────────────────────────────────────────────────────

class EvalTechniqueOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvalTechniqueOffer
        fields = '__all__'


class LockTechniqueSerializer(serializers.Serializer):
    id_soumission = serializers.IntegerField()


# ── Step 6 ────────────────────────────────────────────────────────────────────

class EvalFinanciereOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvalFinanciereOffer
        fields = '__all__'


# ── Step 7 ────────────────────────────────────────────────────────────────────

class ClassementEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassementEntry
        fields = '__all__'


class EcarterProvisionalSerializer(serializers.Serializer):
    id_soumission = serializers.IntegerField()
    motif = serializers.CharField()


# ── Step 8 ────────────────────────────────────────────────────────────────────

class ProcesVerbalSerializer(serializers.ModelSerializer):
    signatures = serializers.SerializerMethodField()

    class Meta:
        model = ProcesVerbal
        fields = ['id', 'id_comission', 'type_pv', 'locked', 'sent_to_sc', 'created_at', 'signatures']

    def get_signatures(self, obj):
        return SignaturePVSerializer(obj.signatures.all(), many=True).data


class SignaturePVSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignaturePV
        fields = '__all__'


class SignerPVSerializer(serializers.Serializer):
    id_utilisateur = serializers.IntegerField()
    reserve = serializers.CharField(required=False, allow_blank=True, default="")


class SCDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCDecision
        fields = '__all__'


class SCDecisionCreateSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['accepted', 'rejected', 'info_request'])
    motif_rejet = serializers.CharField(required=False, allow_blank=True, default="")
    decided_by = serializers.IntegerField()

    def validate(self, attrs):
        if attrs['decision'] == 'rejected' and not attrs.get('motif_rejet', '').strip():
            raise serializers.ValidationError({"motif_rejet": "Motif obligatoire en cas de rejet."})
        return attrs
    

class AssignationCTSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignationCT
        fields = ['id', 'id_comission', 'id_utilisateur', 'assigned_at']

class RapportCTSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapportCT
        fields = ['id', 'id_comission', 'submitted_by', 'methodologie', 'equipe',
                  'materiels', 'anomalies', 'avis_global', 'submitted', 'submitted_at',
                  'created_at', 'updated_at']