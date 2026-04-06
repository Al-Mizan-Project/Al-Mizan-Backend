from rest_framework import serializers


class RecoursCreateSerializer(serializers.Serializer):
    id_operateur_economique = serializers.IntegerField()
    id_validation = serializers.IntegerField()
    id_soumission = serializers.IntegerField()
    motif = serializers.CharField()


class RecoursDecisionSerializer(serializers.Serializer):
    decision = serializers.CharField()
    traite_par = serializers.IntegerField()


class RecoursResponseSerializer(serializers.Serializer):
    id_recours = serializers.IntegerField()
    id_operateur_economique = serializers.IntegerField()
    id_validation = serializers.IntegerField()
    id_soumission = serializers.IntegerField()
    statut = serializers.CharField()
    motif = serializers.CharField()
    decision = serializers.CharField(allow_null=True)
    date_depot = serializers.CharField()
    date_limite = serializers.CharField()
    date_decision = serializers.CharField(allow_null=True)
    traite_par = serializers.IntegerField(allow_null=True)