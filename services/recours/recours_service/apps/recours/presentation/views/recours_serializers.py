from rest_framework import serializers


class RecoursCreateSerializer(serializers.Serializer):
    id_operateur_economique = serializers.IntegerField()
    id_validation = serializers.IntegerField()
    id_soumission = serializers.IntegerField()
    motif = serializers.CharField()


class RecoursResponseSerializer(serializers.Serializer):
    id_recours = serializers.IntegerField()
    statut = serializers.CharField()
    decision = serializers.CharField()