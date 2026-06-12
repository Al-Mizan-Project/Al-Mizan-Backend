
import logging

from auth_service.models import Utilisateur
from appels_service.services.validation_interne import get_commission_interne_dashboard_data
from appels_service.services.validation_externe import get_commission_externe_dashboard_data

logger = logging.getLogger(__name__)


class CommissionAppelsService:
    """Service for retrieving and classifying appels d'offres by commission role."""

    @staticmethod
    def get_appels_for_user(user_id: int = None, role: str = None, membre_id=None) -> dict:
        """
        Main entry point: retrieve appels and classify by state.

        Args:
            user_id: id_utilisateur from JWT token or request query.
            role: RESP_VALID_INTERN or RESP_CM.
            membre_id: direct membership identifier for commission tables.

        Returns:
            A dict containing `stats` and `appels`.
        """
        if membre_id is not None:
            resolved_membre_id = membre_id
        elif user_id is not None:
            user = Utilisateur.objects.filter(id_utilisateur=user_id).first()
            if not user:
                raise ValueError(f"Utilisateur introuvable pour user_id={user_id}.")
            resolved_membre_id = user.id_membre if user.id_membre is not None else user_id
        else:
            raise ValueError("user_id or membre_id is required")

        if resolved_membre_id is None:
            raise ValueError("Unable to resolve membre_id for commission lookup.")

        role_upper = str(role).upper()
        if role_upper == 'RESP_VALID_INTERN':
            return get_commission_interne_dashboard_data(resolved_membre_id)
        if role_upper == 'RESP_CM':
            return get_commission_externe_dashboard_data(resolved_membre_id)

        raise ValueError(f"Role inconnu: {role}")
