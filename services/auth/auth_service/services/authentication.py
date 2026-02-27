import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from auth_service.models import Utilisateur
from auth_service.serializers import consume_password_reset_token, revoke_refresh_token, store_password_reset_token


def authenticate_user(email, password):
    user = Utilisateur.objects.select_related("id_role").filter(email=email).first()
    if not user or not check_password(password, user.password):
        raise AuthenticationFailed("Invalid credentials")
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def logout_user(raw_refresh):
    revoke_refresh_token(raw_refresh)


def change_password(user, old_password, new_password):
    if not user.check_password(old_password):
        raise ValidationError({"old_password": ["Old password is incorrect"]})
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])


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
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
