from django.conf import settings
from rest_framework.permissions import BasePermission


def internal_service_headers() -> dict[str, str]:
    token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
    if not token:
        return {}
    return {"X-Internal-Service-Token": token}


class AuthenticatedOrInternalServicePermission(BasePermission):
    def has_permission(self, request, view):
        expected_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
        provided_token = request.headers.get("X-Internal-Service-Token", "")
        if expected_token and provided_token == expected_token:
            return True

        user = request.user
        return bool(user and user.is_authenticated)
