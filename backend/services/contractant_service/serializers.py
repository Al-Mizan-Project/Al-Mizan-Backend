from django.conf import settings
from rest_framework import serializers
import requests

from .models import (
    CommissionEvaluation,
    CommissionExterne,
    CommissionInterne,
    MembresCommissionEvaluation,
    MembresCommissionInterne,
    MembresCommissionExterne,
    ServiceContractant,
)


def _validate_membre(value):
    acteurs_url = settings.ACTEURS_SERVICE_URL
    if not acteurs_url:
        return value
    url = f"{acteurs_url.rstrip('/')}/membres/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.ACTEURS_SERVICE_TIMEOUT,
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_membre at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_membre does not exist")
    return value


def _validate_tutelle(value):
    acteurs_url = settings.ACTEURS_SERVICE_URL
    if not acteurs_url:
        return value
    url = f"{acteurs_url.rstrip('/')}/tutelles/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.ACTEURS_SERVICE_TIMEOUT,
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_tutelle at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_tutelle does not exist")
    return value


# ── Service Contractant ──────────────────────────────────────────────


class ServiceContractantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceContractant
        fields = ["id_service", "id_tutelle", "categorie", "code_ordonnateur"]
        read_only_fields = ["id_service"]


class ServiceContractantCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceContractant
        fields = ["id_service", "id_tutelle", "categorie", "code_ordonnateur"]
        read_only_fields = ["id_service"]

    def validate_id_tutelle(self, value):
        return _validate_tutelle(value)


class ServiceContractantUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceContractant
        fields = ["id_tutelle", "categorie", "code_ordonnateur"]

    def validate_id_tutelle(self, value):
        return _validate_tutelle(value)


# ── Commission Evaluation ────────────────────────────────────────────


class CommissionEvaluationSerializer(serializers.ModelSerializer):
    id_service = serializers.IntegerField(source="id_service_id", read_only=True)

    class Meta:
        model = CommissionEvaluation
        fields = ["id_comission", "id_service", "nom_comission", "categorie"]
        read_only_fields = ["id_comission"]


class CommissionEvaluationCreateSerializer(serializers.ModelSerializer):
    id_service = serializers.PrimaryKeyRelatedField(queryset=ServiceContractant.objects.all())

    class Meta:
        model = CommissionEvaluation
        fields = ["id_comission", "id_service", "nom_comission", "categorie"]
        read_only_fields = ["id_comission"]


class CommissionEvaluationUpdateSerializer(serializers.ModelSerializer):
    id_service = serializers.PrimaryKeyRelatedField(queryset=ServiceContractant.objects.all(), required=False)

    class Meta:
        model = CommissionEvaluation
        fields = ["id_service", "nom_comission", "categorie"]


# ── Commission Interne ───────────────────────────────────────────────


class CommissionInterneSerializer(serializers.ModelSerializer):
    id_service = serializers.IntegerField(source="id_service_id", read_only=True)

    class Meta:
        model = CommissionInterne
        fields = ["id_comission_interne", "id_service", "nom_comission", "type_comission"]
        read_only_fields = ["id_comission_interne"]


class CommissionInterneCreateSerializer(serializers.ModelSerializer):
    id_service = serializers.PrimaryKeyRelatedField(queryset=ServiceContractant.objects.all())

    class Meta:
        model = CommissionInterne
        fields = ["id_comission_interne", "id_service", "nom_comission", "type_comission"]
        read_only_fields = ["id_comission_interne"]


class CommissionInterneUpdateSerializer(serializers.ModelSerializer):
    id_service = serializers.PrimaryKeyRelatedField(queryset=ServiceContractant.objects.all(), required=False)

    class Meta:
        model = CommissionInterne
        fields = ["id_service", "nom_comission", "type_comission"]


# ── Commission Externe ───────────────────────────────────────────────


class CommissionExterneSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionExterne
        fields = ["id_comission_externe", "nom_comission", "niveau_competance", "seuils_competence_financiere"]
        read_only_fields = ["id_comission_externe"]


# ── Membres Commission (junction tables) ─────────────────────────────


class MembresCommissionEvaluationSerializer(serializers.ModelSerializer):
    id_comission = serializers.IntegerField(source="id_comission_id", read_only=True)

    class Meta:
        model = MembresCommissionEvaluation
        fields = ["id", "id_membre", "id_comission"]
        read_only_fields = ["id"]


class MembresCommissionInterneSerializer(serializers.ModelSerializer):
    id_comission_interne = serializers.IntegerField(source="id_commision_interne_id", read_only=True)
    id_service = serializers.SerializerMethodField()
    id_utilisateur = serializers.SerializerMethodField()
    nom = serializers.SerializerMethodField()
    prenom = serializers.SerializerMethodField()
    fonction = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = MembresCommissionInterne
        fields = ["id", "id_membre", "id_comission_interne", "id_service", "id_utilisateur", "nom", "prenom", "fonction", "role"]
        read_only_fields = ["id"]

    def _user(self, obj):
        try:
            from auth_service.models import Utilisateur
            return Utilisateur.objects.select_related("id_role").filter(id_utilisateur=obj.id_membre).first()
        except Exception:
            return None

    def _membre(self, obj):
        user = self._user(obj)
        if not user or not user.id_membre:
            return None
        try:
            from acteurs_service.models import Membre
            return Membre.objects.filter(id_membre=user.id_membre).first()
        except Exception:
            return None

    def get_id_service(self, obj):
        try:
            return obj.id_commision_interne.id_service_id
        except Exception:
            return None

    def get_id_utilisateur(self, obj):
        return obj.id_membre

    def get_nom(self, obj):
        membre = self._membre(obj)
        return membre.nom if membre else None

    def get_prenom(self, obj):
        membre = self._membre(obj)
        return membre.prenom if membre else None

    def get_fonction(self, obj):
        membre = self._membre(obj)
        return membre.fonction if membre else None

    def get_role(self, obj):
        user = self._user(obj)
        return user.id_role.nom_role if user and user.id_role else None


class MembresCommissionExterneSerializer(serializers.ModelSerializer):
    id_commission_externe = serializers.IntegerField(source="id_comission_externe_id", read_only=True)
    id_utilisateur = serializers.SerializerMethodField()
    nom = serializers.SerializerMethodField()
    prenom = serializers.SerializerMethodField()
    fonction = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = MembresCommissionExterne
        fields = ["id", "id_membre", "id_commission_externe", "id_utilisateur", "nom", "prenom", "fonction", "role"]
        read_only_fields = ["id"]

    def _user(self, obj):
        try:
            from auth_service.models import Utilisateur
            return Utilisateur.objects.select_related("id_role").filter(id_utilisateur=obj.id_membre).first()
        except Exception:
            return None

    def _membre(self, obj):
        user = self._user(obj)
        if not user or not user.id_membre:
            return None
        try:
            from acteurs_service.models import Membre
            return Membre.objects.filter(id_membre=user.id_membre).first()
        except Exception:
            return None

    def get_id_utilisateur(self, obj):
        return obj.id_membre

    def get_nom(self, obj):
        membre = self._membre(obj)
        return membre.nom if membre else None

    def get_prenom(self, obj):
        membre = self._membre(obj)
        return membre.prenom if membre else None

    def get_fonction(self, obj):
        membre = self._membre(obj)
        return membre.fonction if membre else None

    def get_role(self, obj):
        user = self._user(obj)
        return user.id_role.nom_role if user and user.id_role else None
