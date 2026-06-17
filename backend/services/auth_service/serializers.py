import hashlib
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import password_validation
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
import requests

from .models import Utilisateur, Role, Permission, PermissionRole
from .rbac import normalize_role_name, permissions_for_role
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
    token["must_change_password"] = bool(user.must_change_password)
    token["id_membre"] = str(user.id_membre) if user.id_membre else ""



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
        fields = ["id_utilisateur", "id_role", "id_membre", "email", "is_active", "must_change_password", "created_at", "updated_at"]
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
        fields = ["id_utilisateur", "id_role", "id_membre", "email", "is_active", "must_change_password", "created_at", "updated_at"]

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
    language = serializers.ChoiceField(choices=["en", "fr", "ar"], default="fr")


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=12)


class RolePermissionsReplaceSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)


class UserPermissionsReplaceSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    permission_names = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        attrs.setdefault("permission_ids", [])
        attrs.setdefault("permission_names", [])
        return attrs


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


def delete_password_reset_token(raw_token):
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    cache.delete(f"auth:pwdreset:{digest}")


def store_account_activation_token(raw_token, user_id, timeout_seconds=None):
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    timeout = timeout_seconds or int(getattr(settings, "ACCOUNT_ACTIVATION_TTL", 86400))
    cache.set(f"auth:activate:{digest}", str(user_id), timeout=timeout)


def consume_account_activation_token(raw_token):
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    key = f"auth:activate:{digest}"
    user_id = cache.get(key)
    if not user_id:
        return None
    cache.delete(key)
    return int(user_id)


def build_activation_url(token):
    base_url = getattr(settings, "ACCOUNT_ACTIVATION_URL", "").rstrip("/")
    return f"{base_url}?{urlencode({'token': token})}"


def build_password_reset_url(token):
    base_url = getattr(settings, "FRONTEND_PASSWORD_RESET_URL", "").rstrip("/")
    return f"{base_url}?{urlencode({'token': token})}"


PASSWORD_RESET_EMAILS = {
    "en": {
        "subject": "Reset your Al-Mizan password",
        "lines": [
            "We received a request to reset your password.",
            "Reset link: {reset_url}",
            "If you did not request this, you can ignore this email.",
        ],
    },
    "fr": {
        "subject": "Reinitialisation de votre mot de passe Al-Mizan",
        "lines": [
            "Une demande de reinitialisation de mot de passe a ete recue.",
            "Lien de reinitialisation: {reset_url}",
            "Si vous n'etes pas a l'origine de cette demande, ignorez cet email.",
        ],
    },
    "ar": {
        "subject": "إعادة تعيين كلمة مرور الميزان",
        "lines": [
            "تلقينا طلبا لإعادة تعيين كلمة المرور الخاصة بك.",
            "رابط إعادة التعيين: {reset_url}",
            "إذا لم تطلب ذلك، يمكنك تجاهل هذه الرسالة.",
        ],
    },
}


def send_password_reset_email(user, reset_url, language):
    content = PASSWORD_RESET_EMAILS[language]
    send_mail(
        subject=content["subject"],
        message="\n".join(line.format(reset_url=reset_url) for line in content["lines"]),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_activation_email(user, activation_url, temporary_password=None):
    lines = [
        "Votre compte Al-Mizan a ete cree.",
        f"Lien d'activation: {activation_url}",
    ]
    if temporary_password:
        lines.append(f"Mot de passe temporaire: {temporary_password}")
    lines.append("Vous devrez changer ce mot de passe apres votre premiere connexion.")
    send_mail(
        subject="Activation de votre compte Al-Mizan",
        message="\n".join(lines),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=True,
    )


class InternalActeurRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    id_membre = serializers.CharField()
    role_nom = serializers.CharField(required=False) # Le nom du rôle en texte (ex: "SERVICE Contractant")
    role = serializers.CharField(required=False, write_only=True)
    permission = serializers.CharField(required=False, allow_blank=True, write_only=True)
    permissions = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    send_activation = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        role_name = normalize_role_name(attrs.get("role_nom") or attrs.get("role"))
        if not role_name:
            raise serializers.ValidationError({"role_nom": ["This field is required."]})
        try:
            attrs["role_nom"] = Role.objects.get(nom_role=role_name)
        except Role.DoesNotExist:
            raise serializers.ValidationError(
                {"role_nom": [f"Le rôle '{role_name}' n'existe pas dans le service Auth."]}
            )

        permissions = list(attrs.get("permissions") or [])
        single_permission = (attrs.get("permission") or "").strip()
        if single_permission:
            permissions.append(single_permission)
        attrs["permissions"] = permissions
        return attrs

    def create(self, validated_data):
        role = validated_data.pop('role_nom')
        validated_data.pop("role", None)
        validated_data.pop("permission", None)
        validated_data.pop('permissions', [])
        send_activation = validated_data.pop("send_activation", True)
        raw_password = validated_data.get("password") or secrets.token_urlsafe(12)
        self.temporary_password = raw_password
        
        with transaction.atomic():
            user = Utilisateur(
                email=validated_data['email'],
                id_membre=validated_data['id_membre'],
                id_role=role,
                is_active=not send_activation,
                must_change_password=send_activation,
            )
            user.set_password(raw_password)
            user.save()

            for permission_name in permissions_for_role(role.nom_role):
                permission, _ = Permission.objects.get_or_create(nom_permission=permission_name)
                PermissionRole.objects.get_or_create(id_role=role, id_permission=permission)

        self.activation_url = None
        if send_activation:
            token = secrets.token_urlsafe(48)
            store_account_activation_token(token, user.id_utilisateur)
            self.activation_url = build_activation_url(token)
            send_activation_email(user, self.activation_url, temporary_password=raw_password)

        return user
