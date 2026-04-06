from django.conf import settings
from rest_framework.permissions import BasePermission

from auth_service.services.access_control import user_permission_names


ADMIN_ROLE_NAMES = {"admin", "administrator", "superadmin", "super_admin"}


class AuthServicePermission(BasePermission):
    def has_permission(self, request, view):
        internal_token = request.headers.get("X-Internal-Service-Token", "")
        expected_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
        if request.method in {"GET", "HEAD", "OPTIONS"} and expected_token and internal_token == expected_token:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role_name = getattr(getattr(user, "id_role", None), "nom_role", "").strip().lower()
        if role_name in ADMIN_ROLE_NAMES:
            return True
        required_permissions = getattr(view, "required_permissions", {})
        required = required_permissions.get(request.method)
        if not required:
            return True
        return set(required).issubset(set(user_permission_names(user)))
