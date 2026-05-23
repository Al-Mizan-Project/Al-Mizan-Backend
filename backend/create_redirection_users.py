import os
import django
import uuid

# =========================
# CONFIG DJANGO
# =========================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from auth_service.models import Utilisateur, Role
from django.contrib.auth.hashers import make_password


# =========================
# CONFIGURATION
# =========================
DEFAULT_PASSWORD = "AlMizan2026"

# Rôles utilisés (uniquement validateurs)
roles_to_test = [
    'VALIDATEUR_INTERNE',
    'VALIDATEUR_EXTERNE'
]

# Utilisateurs (UNIQUEMENT validateurs)
users_to_create = [

    {
        "email": "validateur_interne_1@almizan.dz",
        "role": "VALIDATEUR_INTERNE"
    },
    {
        "email": "validateur_externe_1@almizan.dz",
        "role": "VALIDATEUR_EXTERNE"
    }
]


# =========================
# LOGIQUE PRINCIPALE
# =========================
def create_test_users():

    # Création / récupération des rôles
    role_objs = {}
    for role_name in roles_to_test:
        role, _ = Role.objects.get_or_create(nom_role=role_name)
        role_objs[role_name] = role

    # Création / mise à jour des utilisateurs
    for udata in users_to_create:

        email = udata["email"]
        role_name = udata["role"]

        role_obj = role_objs.get(role_name)

        if not role_obj:
            print(f"Rôle introuvable pour {email}: {role_name}")
            continue

        user, created = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                "id_membre": str(uuid.uuid4()),
                "id_role": role_obj,
                "password": make_password(DEFAULT_PASSWORD),
                "is_active": True
            }
        )

        if created:
            print(f"Créé: {email} ({role_name})")
        else:
            user.id_role = role_obj
            user.set_password(DEFAULT_PASSWORD)
            user.is_active = True
            user.save()
            print(f"Mis à jour: {email} ({role_name})")


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    try:
        create_test_users()
        print("\nTous les validateurs ont été générés avec succès !")

    except Exception as e:
        print(f"Erreur: {e}")