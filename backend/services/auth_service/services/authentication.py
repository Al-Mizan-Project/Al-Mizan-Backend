import secrets

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from auth_service.models import Utilisateur
from auth_service.serializers import (
    apply_user_claims,
    consume_account_activation_token,
    consume_password_reset_token,
    revoke_refresh_token,
    store_password_reset_token,
)


def authenticate_user(email, password):
    email = (email or "").strip().lower()
    user = Utilisateur.objects.select_related("id_role").filter(email=email).first()
    
    if not user or not check_password(password, user.password):
        raise AuthenticationFailed("Invalid credentials")
    if not user.is_active:
        raise AuthenticationFailed("Account is not activated")
        
    refresh = RefreshToken.for_user(user)
    apply_user_claims(refresh, user)
    update_last_login(None, user)
    
    # On ajoute les infos de l'utilisateur ici
    return {
        "access": str(refresh.access_token), 
        "refresh": str(refresh),
        "user": {
            "email": user.email,
            "id_membre": str(user.id_membre) if user.id_membre else None,
            "role": user.id_role.nom_role if user.id_role else None,
            "must_change_password": bool(user.must_change_password),
        }
    }


def logout_user(raw_refresh):
    revoke_refresh_token(raw_refresh)


def change_password(user, old_password, new_password):
    if not user.check_password(old_password):
        raise ValidationError({"old_password": ["Old password is incorrect"]})
    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])


def initiate_password_reset(email):
    payload = {"detail": "If that account exists, a reset flow has been initiated"}
    user = Utilisateur.objects.only("id_utilisateur").filter(email=email).first()
    if user:
        token = secrets.token_urlsafe(48)
        store_password_reset_token(
            token,
            user.id_utilisateur,
            timeout_seconds=int(getattr(settings, "PASSWORD_RESET_TOKEN_TTL", 900)),
        )
        if settings.DEBUG:
            payload["reset_token"] = token
    return payload


def complete_password_reset(token, new_password):
    user_id = consume_password_reset_token(token)
    if not user_id:
        raise ValidationError({"token": ["Invalid or expired reset token"]})
    user = Utilisateur.objects.filter(id_utilisateur=user_id).first()
    if not user:
        raise NotFound("User not found")
    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])


def activate_account(token):
    user_id = consume_account_activation_token(token)
    if not user_id:
        raise ValidationError({"token": ["Invalid or expired activation token"]})
    user = Utilisateur.objects.filter(id_utilisateur=user_id).first()
    if not user:
        raise NotFound("User not found")
    user.is_active = True
    user.must_change_password = True
    user.save(update_fields=["is_active", "must_change_password", "updated_at"])
    return user
