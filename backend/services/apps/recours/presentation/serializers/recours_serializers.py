from rest_framework import serializers


TYPE_RECOURS_CHOICES = ["GRACIEUX", "HIERARCHIQUE", "CONTENTIEUX"]


class RecoursCreateSerializer(serializers.Serializer):
    id_operateur_economique = serializers.IntegerField()
    id_soumission = serializers.IntegerField()
    motif = serializers.CharField()
    type_recours = serializers.ChoiceField(
        choices=TYPE_RECOURS_CHOICES, required=False, allow_null=True, default=None
    )
    objet = serializers.CharField(required=False, allow_blank=True, default="")
    explications = serializers.CharField(required=False, allow_blank=True, default="")
    document_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    # Optional: if the client already knows which validation is being contested.
    # When omitted, the server derives it from the soumission.
    id_validation = serializers.IntegerField(required=False, allow_null=True, default=None)


class RecoursDecisionSerializer(serializers.Serializer):
    decision = serializers.CharField()
    traite_par = serializers.IntegerField()


class RecoursUpdateSerializer(serializers.Serializer):
    motif = serializers.CharField(required=False, allow_blank=True)
    type_recours = serializers.ChoiceField(
        choices=TYPE_RECOURS_CHOICES, required=False, allow_null=True
    )
    objet = serializers.CharField(required=False, allow_blank=True)
    explications = serializers.CharField(required=False, allow_blank=True)
    document_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )


class RecoursResponseSerializer(serializers.Serializer):
    id_recours = serializers.IntegerField()
    id_operateur_economique = serializers.IntegerField()
    id_validation = serializers.IntegerField(allow_null=True)
    id_soumission = serializers.IntegerField()
    statut = serializers.CharField()
    motif = serializers.CharField()
    type_recours = serializers.CharField(allow_null=True)
    objet = serializers.CharField(allow_blank=True)
    explications = serializers.CharField(allow_blank=True)
    document_ids = serializers.ListField(child=serializers.IntegerField())
    decision = serializers.CharField(allow_null=True)
    date_depot = serializers.CharField()
    date_limite = serializers.CharField()
    date_decision = serializers.CharField(allow_null=True)
    traite_par = serializers.IntegerField(allow_null=True)
