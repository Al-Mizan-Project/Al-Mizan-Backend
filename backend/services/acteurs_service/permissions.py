from rest_framework.permissions import BasePermission

class IsAdminRole(BasePermission):
    """
    Vérifie si l'utilisateur possède le rôle 'Admin'.
    Utilisé pour la création des organisations et des responsables.
    """
    def has_permission(self, request, view):
        # On vérifie d'abord si l'utilisateur est connecté
        if not request.user or not request.user.is_authenticated:
            return False
            
        # On lit le rôle depuis le token JWT (request.auth) ou depuis l'objet user
        # Exemple si votre token contient { "user_id": 1, "role": "Admin", ... }
        token_payload = request.auth or {}
        role = token_payload.get('role') or getattr(request.user, 'role', None)
        
        return role == "Admin"


class IsResponsable(BasePermission):
    """
    Vérifie si l'utilisateur a une permission de type 'responsable_...'.
    Utilisé pour la création des collaborateurs.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # On récupère la liste des permissions contenues dans le token
        token_payload = request.auth or {}
        permissions = token_payload.get('permissions', [])
        
        # Si vous l'avez attaché à request.user via un middleware custom :
        if not permissions and hasattr(request.user, 'permissions'):
            permissions = request.user.permissions
            
        # On vérifie s'il possède au moins une permission commençant par "responsable_"
        # (ex: responsable_service_contratant, responsable_tutelle, etc.)
        for perm in permissions:
            if perm.startswith("responsable_"):
                return True
                
        return False