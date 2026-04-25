from django.conf import settings
from rest_framework.permissions import BasePermission


ADMIN_ROLE_NAMES = {"admin", "administrator", "superadmin", "super_admin"}


class ActeursServicePermission(BasePermission):
    def has_permission(self, request, view):
        internal_token = request.headers.get("X-Internal-Service-Token", "")
        expected_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
        if request.method in {"GET", "HEAD", "OPTIONS"} and expected_token and internal_token == expected_token:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        token = request.auth
        role_name = str(token.get("role", "")).strip().lower() if token else ""
        if role_name in ADMIN_ROLE_NAMES:
            return True
        required_permissions = getattr(view, "required_permissions", {})
        required = required_permissions.get(request.method)
        if not required:
            return True
        granted_permissions = set(token.get("permissions", [])) if token else set()
        return set(required).issubset(granted_permissions)
