from rest_framework import serializers
from .models import Membre


class MembreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membre
        fields = ["id_membre", "id_organisation", "prenom", "nom", "telephone", "fonction", "created_at", "updated_at"]
        read_only_fields = ["id_membre", "created_at", "updated_at"]
