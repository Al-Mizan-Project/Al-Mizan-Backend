from django.conf import settings
from django.contrib.auth import password_validation
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
import requests
import hashlib

from .models import Utilisateur, Role, Permission, PermissionRole
from .services.access_control import user_permission_names


def validate_membre_reference(value):
    membres_service_url = settings.MEMBRES_SERVICE_URL
    if not membres_service_url:
        return value
    url = f"{membres_service_url.rstrip('/')}/membres/{value}"
    try:
        response = requests.get(
            url,
            timeout=settings.MEMBRES_SERVICE_TIMEOUT,
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
        )
    except requests.RequestException:
        raise serializers.ValidationError("Unable to validate id_membre at this time")
    if response.status_code != 200:
        raise serializers.ValidationError("id_membre does not exist")
    return value


def apply_user_claims(token, user):
    token["email"] = user.email
    token["role"] = user.id_role.nom_role
    token["permissions"] = user_permission_names(user)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id_role", "nom_role"]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id_permission", "nom_permission"]


class PermissionRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionRole
        fields = ["id_role", "id_permission"]


class UtilisateurSerializer(serializers.ModelSerializer):
    id_role = serializers.IntegerField(source="id_role_id", read_only=True)

    class Meta:
        model = Utilisateur
        fields = ["id_utilisateur", "id_role", "id_membre", "email", "created_at", "updated_at"]
        read_only_fields = ["id_utilisateur", "created_at", "updated_at"]


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    id_role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())
    password = serializers.CharField(write_only=True, min_length=12)

    class Meta:
        model = Utilisateur
        fields = ["id_utilisateur", "id_role", "id_membre", "email", "password", "created_at", "updated_at"]
        read_only_fields = ["id_utilisateur", "created_at", "updated_at"]

    def validate_id_membre(self, value):
        return validate_membre_reference(value)

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = Utilisateur(**validated_data)
        try:
            password_validation.validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        user.set_password(password)
        user.save()
        return user


class UtilisateurUpdateSerializer(serializers.ModelSerializer):
    id_role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)

    class Meta:
        model = Utilisateur
        fields = ["id_role", "id_membre", "email"]

    def validate_id_membre(self, value):
        return validate_membre_reference(value)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=12)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=12)


class RolePermissionsReplaceSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)


class UserRoleUpdateSerializer(serializers.Serializer):
    id_role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())


class RedisAwareTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        raw_refresh = attrs.get("refresh")
        try:
            token = RefreshToken(raw_refresh)
        except TokenError as exc:
            raise serializers.ValidationError({"refresh": [str(exc)]})
        jti = token.get("jti")
        key = f"auth:revoked:{jti}"
        if cache.get(key):
            raise serializers.ValidationError({"detail": "Token has been revoked"})
        data = super().validate(attrs)
        user_id = token.get("user_id")
        user = Utilisateur.objects.select_related("id_role").filter(id_utilisateur=user_id).first()
        if user:
            access_token = token.access_token
            apply_user_claims(access_token, user)
            data["access"] = str(access_token)
        return data


def revoke_refresh_token(raw_refresh):
    try:
        token = RefreshToken(raw_refresh)
    except TokenError as exc:
        raise serializers.ValidationError({"refresh": [str(exc)]})
    exp = token.get("exp")
    jti = token.get("jti")
    ttl = max(0, int(exp - timezone.now().timestamp()))
    key = f"auth:revoked:{jti}"
    cache.set(key, "1", timeout=ttl)


def store_password_reset_token(raw_token, user_id, timeout_seconds=900):
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    cache.set(f"auth:pwdreset:{digest}", str(user_id), timeout=timeout_seconds)


def consume_password_reset_token(raw_token):
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    key = f"auth:pwdreset:{digest}"
    user_id = cache.get(key)
    if not user_id:
        return None
    cache.delete(key)
    return int(user_id)
