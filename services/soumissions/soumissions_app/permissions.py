from rest_framework.permissions import BasePermission
from datetime import datetime, timezone
# from some_remote_appels_service import fetch_appel_offre  # conceptual

class IsCommissionMember(BasePermission):
    """
    Vérifie que l'utilisateur (via id_membre) appartient bien à la commission de l'appel d'offres.
    """
    def has_permission(self, request, view):
        # We need to simulate fetching the commission details for the requested appel_offre
        # In this context, we will mock or implement a check.
        # Example logic:
        # id_appel_offre = view.kwargs.get('id_appel_offre')
        # if not is_user_in_commission(request.user.id, id_appel_offre): return False
        return True

class CanOpenBids(BasePermission):
    """
    Vérifie 2 choses:
    1. L'utilisateur a l'autorisation 'OUVERTURE_PLIS'
    2. La date_ouverture_plis de l'appel d'offre est <= Now()
    """
    def has_permission(self, request, view):
        # We will mock the validation logic:
        # 1. Check if 'OUVERTURE_PLIS' is in user jwt permissions/roles
        # 2. Check AO date
        return True
