from rest_framework import serializers

from .models import DetectionAnomalieIA


class DetectionAnomalieIASerializer(serializers.ModelSerializer):
    class Meta:
        model = DetectionAnomalieIA
        fields = "__all__"


class DetecterAnomaliesInputSerializer(serializers.Serializer):
    id_appel_offre = serializers.IntegerField()
    soumissions = serializers.ListField(child=serializers.DictField(), required=False)


class StatutExamenPatchSerializer(serializers.Serializer):
    statut_examen = serializers.CharField(max_length=30)


class VerifierConformiteInputSerializer(serializers.Serializer):
    required_documents = serializers.ListField(child=serializers.CharField(max_length=100), required=False)
    provided_documents = serializers.ListField(child=serializers.DictField(), required=False)


class CdcRedigerInputSerializer(serializers.Serializer):
    besoin = serializers.CharField(max_length=5000)
    type_procedure = serializers.CharField(max_length=100)
    contraintes = serializers.ListField(child=serializers.CharField(max_length=1000), required=False)


class CdcReviserInputSerializer(serializers.Serializer):
    texte = serializers.CharField(max_length=20000)