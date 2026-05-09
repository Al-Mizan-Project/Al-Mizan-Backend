import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Le script utilisera les variables d'environnement passées dans le terminal
# (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)

django.setup()

from auth_service.models import Utilisateur, Role
from django.contrib.auth.hashers import make_password

def create_test_users():
    # 1. Ensure Roles exist
    roles = ['admin', 'service_contractant', 'commission_externe', 'tutelle']
    role_objs = {}
    for rname in roles:
        role, _ = Role.objects.get_or_create(nom_role=rname)
        role_objs[rname] = role
    
    # 2. Test Data
    users_to_create = [
        {
            "email": "responsable.tutelle@ministere.dz",
            "id_membre": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33",
            "role": role_objs['tutelle']
        },
        {
            "email": "responsable.externe@commission.dz",
            "id_membre": "d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44",
            "role": role_objs['commission_externe']
        }
    ]
    
    for udata in users_to_create:
        user, created = Utilisateur.objects.get_or_create(
            email=udata['email'],
            defaults={
                "id_membre": udata['id_membre'],
                "id_role": udata['role'],
                "password": make_password("AlMizan2026")
            }
        )
        if created:
            print(f"User {udata['email']} created successfully.")
        else:
            # Update password and id_membre if already exists
            user.id_membre = udata['id_membre']
            user.id_role = udata['role']
            user.set_password("AlMizan2026")
            user.save()
            print(f"User {udata['email']} updated successfully.")

if __name__ == "__main__":
    try:
        create_test_users()
    except Exception as e:
        print(f"Error: {e}")
