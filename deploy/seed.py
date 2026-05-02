from django.db import transaction
from auth_service.models import Role, Permission, PermissionRole, Utilisateur

def run_seed():
    with transaction.atomic():
        print("Création des rôles...")
        role_admin = Role.objects.get_or_create(nom_role="Admin")[0]
        role_sc = Role.objects.get_or_create(nom_role="SERVICE Contractant")[0]
        role_ce = Role.objects.get_or_create(nom_role="Commission Externe")[0]
        role_tutelle = Role.objects.get_or_create(nom_role="Tutelle")[0]
        role_oe = Role.objects.get_or_create(nom_role="Operateur Economique")[0]

        print("Création des permissions...")
        perm_sc = Permission.objects.get_or_create(nom_permission="responsable_service_contratant")[0]
        perm_ce = Permission.objects.get_or_create(nom_permission="responsable_commission_externe")[0]
        perm_tutelle = Permission.objects.get_or_create(nom_permission="responsable_tutelle")[0]
        perm_oe = Permission.objects.get_or_create(nom_permission="responsable_operateur_economique")[0]

        print("Liaison rôles <-> permissions...")
        PermissionRole.objects.get_or_create(id_role=role_sc, id_permission=perm_sc)
        PermissionRole.objects.get_or_create(id_role=role_ce, id_permission=perm_ce)
        PermissionRole.objects.get_or_create(id_role=role_tutelle, id_permission=perm_tutelle)
        PermissionRole.objects.get_or_create(id_role=role_oe, id_permission=perm_oe)

        print("Création de l'Administrateur...")
        if not Utilisateur.objects.filter(email="admin@plateforme.dz").exists():
            admin = Utilisateur(
                email="admin@plateforme.dz",
                id_membre="00000000-0000-0000-0000-000000000000",
                id_role=role_admin,
                is_active=True
            )
            admin.set_password("Admin123!")
            admin.save()
            print("=> Compte Admin créé avec succès !")
        else:
            print("=> Le compte Admin existe déjà.")

    print("=== INITIALISATION TERMINEE ===")

run_seed()