import logging

from rest_framework.permissions import BasePermission
from django.utils import timezone
from auth_service.rbac import normalize_role_name

from .services.integrations import validate_appel_offre

logger = logging.getLogger(__name__)


class IsCommissionMember(BasePermission):
    """
    Vérifie que l'utilisateur appartient à la commission de l'appel d'offres.
    Checks JWT claims for role and calls the Appels service for commission membership.
    Graceful degradation: allows if the Appels service is unreachable.
    """

    def has_permission(self, request, view):
        token_payload = getattr(request, "auth", None) or {}
        role = normalize_role_name(token_payload.get("role", ""))

        # Admin / commission roles are always allowed
        if role in ("ADMIN", "EVALUATEUR", "RESP_CM", "VALIDATEUR_EXTERNE_MARCHE", "VALIDATEUR_EXTERNE_CDC", "MEMBRE_COMITE_TECHNIQUE"):
            return True

        id_appel_offre = view.kwargs.get("id_appel_offre")
        if not id_appel_offre:
            return False

        user_id = token_payload.get("user_id")
        if not user_id:
            return False

        exists, data = validate_appel_offre(id_appel_offre)
        if not exists:
            return False

        if data is None:
            # Service unreachable — graceful degradation
            logger.warning(
                "Appels service unreachable; allowing commission check for user %s",
                user_id,
            )
            return True

        # Check if user_id is in the commission members list returned by appels service
        commission = data.get("commission", {})
        membres = commission.get("membres", [])
        if not membres:
            # AO data doesn't contain commission info — allow (backward compat)
            return True

        member_ids = set()
        for m in membres:
            mid = m.get("id_utilisateur") or m.get("id_membre") or m.get("id")
            if mid is not None:
                member_ids.add(int(mid))

        return int(user_id) in member_ids


class CanOpenBids(BasePermission):
    """
    Vérifie 2 choses :
    1. L'utilisateur possède la permission 'OUVERTURE_PLIS' dans son JWT.
    2. La date_ouverture_plis de l'appel d'offre est <= maintenant.
    Graceful degradation on service unavailability.
    """

    def has_permission(self, request, view):
        token_payload = getattr(request, "auth", None) or {}
        permissions = token_payload.get("permissions", [])
        role = normalize_role_name(token_payload.get("role", ""))

        # Check permission claim
        if "pli:open" not in permissions and "OUVERTURE_PLIS" not in permissions and role not in ("ADMIN",):
            return False

        id_appel_offre = view.kwargs.get("id_appel_offre")
        if not id_appel_offre:
            return False

        exists, data = validate_appel_offre(id_appel_offre)
        if not exists:
            return False
        if data is None:
            logger.warning(
                "Appels service unreachable; skipping date check for AO %s",
                id_appel_offre,
            )
            return True

        date_ouverture = data.get("date_ouverture_plis")
        if not date_ouverture:
            return True

        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(str(date_ouverture))
        if dt is None:
            return True
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)

        if timezone.now() < dt:
            return False

        return True
