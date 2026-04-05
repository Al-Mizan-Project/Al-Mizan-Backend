from rest_framework import serializers

from .models import Membre, OperateurEconomique, Organisation, Tutelle
from .services.organisations import SERVICE_CONTRACTANT_PRIMARY_TYPE, is_service_contractant_type


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id_organisation", "nom_officiel", "adresse_siege", "email_contact", "type_entite"]
        read_only_fields = ["id_organisation"]


class ServiceContractantSerializer(serializers.ModelSerializer):
    type_entite = serializers.CharField(required=False, default=SERVICE_CONTRACTANT_PRIMARY_TYPE)

    class Meta:
        model = Organisation
        fields = ["id_organisation", "nom_officiel", "adresse_siege", "email_contact", "type_entite"]
        read_only_fields = ["id_organisation"]

    def validate_type_entite(self, value):
        if not is_service_contractant_type(value):
            raise serializers.ValidationError("type_entite must be a service contractant type")
        return SERVICE_CONTRACTANT_PRIMARY_TYPE

    def validate(self, attrs):
        if "type_entite" not in attrs:
            attrs["type_entite"] = SERVICE_CONTRACTANT_PRIMARY_TYPE
        return attrs


class OperateurEconomiqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperateurEconomique
        fields = [
            "id_operateur_economique",
            "nif",
            "registre_commerce_num",
            "casnos_vrt",
            "cnas_vrt",
            "rib_bancaire",
        ]
        read_only_fields = ["id_operateur_economique"]


class MembreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membre
        fields = ["id_membre", "id_organisation", "prenom", "nom", "telephone", "fonction", "created_at", "updated_at"]
        read_only_fields = ["id_membre", "created_at", "updated_at"]

    def validate_id_organisation(self, value):
        if value is None:
            return value
        if not Organisation.objects.filter(id_organisation=value).exists():
            raise serializers.ValidationError("id_organisation does not exist")
        return value


class TutelleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tutelle
        fields = ["id_tutelle", "nom_tutelle", "identite_autorite"]
        read_only_fields = ["id_tutelle"]
