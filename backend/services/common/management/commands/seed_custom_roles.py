from django.core.management.base import BaseCommand
from django.db import transaction
import uuid

# auth_service
from auth_service.models import Role, Permission, PermissionRole, Utilisateur

# acteurs_service
from acteurs_service.models import (
    Organisation, Membre, TypeEntite, 
    ServiceContractant as ActeursServiceContractant, 
    CommissionExterne as ActeursCommissionExterne, 
    Tutelle as ActeursTutelle,
    MembresTutelle
)

# contractant_service
from contractant_service.models import (
    ServiceContractant as ContServiceContractant, 
    CommissionInterne, 
    CommissionExterne as ContCommissionExterne, 
    MembresCommissionInterne, 
    MembresCommissionExterne
)


class Command(BaseCommand):
    help = "Seed custom roles, permissions, commissions, and users based on user request."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Flush existing custom seeded data")

    def _get_uuid(self, int_val):
        return uuid.UUID(int=int_val)

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("--- FETCHING EXISTING ROLES ---")
        try:
            role_sc = Role.objects.get(nom_role="SERVICE Contractant")
            role_ce = Role.objects.get(nom_role="Commission Externe")
            role_tut = Role.objects.get(nom_role="Tutelle")
            role_admin = Role.objects.get(nom_role="Admin")
            role_op = Role.objects.get(nom_role="Operateur Economique")
        except Role.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f"Role missing: {e}. Please ensure roles are created first."))
            return

        # 1. Create Organizations
        org_sc, _ = Organisation.objects.get_or_create(nom_officiel="SC Demo", defaults={"type_entite": TypeEntite.SERVICE_CONTRACTANT})
        org_ce, _ = Organisation.objects.get_or_create(nom_officiel="CE Demo", defaults={"type_entite": TypeEntite.COMMISSION_EXTERNE})
        org_tut, _ = Organisation.objects.get_or_create(nom_officiel="Tutelle Demo", defaults={"type_entite": TypeEntite.TUTELLE})
        org_op, _ = Organisation.objects.get_or_create(nom_officiel="OP Demo", defaults={"type_entite": TypeEntite.OPERATEUR_ECONOMIQUE})

        # 2. Setup Commissions (Contractant Service)
        cont_sc, _ = ContServiceContractant.objects.get_or_create(code_ordonnateur="ORD-01", defaults={"id_tutelle": 1, "categorie": "A"})
        comm_int, _ = CommissionInterne.objects.get_or_create(id_service=cont_sc, nom_comission="Commission Interne Test")
        cont_ce, _ = ContCommissionExterne.objects.get_or_create(nom_comission="Commission Externe Test")

        # 3. Create Specific Users for Redirection Testing
        DEFAULT_PASSWORD = "password123"

        def create_user_group(base_id, role, org, prefix, functions, link_func=None):
            for i, fonction in enumerate(functions):
                m_id_int = base_id + i
                m_uuid = self._get_uuid(m_id_int)
                email = f"{prefix}_{i}@al-mizan.dz"
                if i == 0: email = f"responsable_{prefix}@al-mizan.dz"

                membre, created = Membre.objects.get_or_create(
                    id_membre=m_uuid,
                    defaults={"organisation": org, "nom": prefix.capitalize(), "prenom": fonction, "fonction": fonction}
                )
                if not created:
                    membre.fonction = fonction
                    membre.save()
                
                user, _ = Utilisateur.objects.get_or_create(email=email, defaults={"id_role": role, "id_membre": m_uuid})
                user.set_password(DEFAULT_PASSWORD)
                user.id_role = role
                user.save()
                
                if link_func: link_func(m_id_int, m_uuid)
                self.stdout.write(f"Created {email} (id_membre: {m_id_int if not isinstance(m_uuid, uuid.UUID) else m_uuid}) with fonction '{fonction}'")

        # --- A. SERVICE CONTRACTANT (Interne) ---
        # 1 Responsable + 2 Membres
        def link_int(m_id, m_uuid): MembresCommissionInterne.objects.get_or_create(id_membre=m_id, id_commision_interne=comm_int)
        create_user_group(1000, role_sc, org_sc, "interne", ["responsable_commission_interne", "membre_commission_interne", "membre_commission_interne"], link_int)

        # --- B. COMMISSION EXTERNE ---
        # 1 Responsable + 2 Membres
        def link_ext(m_id, m_uuid): MembresCommissionExterne.objects.get_or_create(id_membre=m_id, id_comission_externe=cont_ce)
        create_user_group(2000, role_ce, org_ce, "externe", ["responsable", "membre", "membre"], link_ext)

        # --- C. TUTELLE ---
        # 1 Responsable + 2 Membres
        def link_tut(m_id, m_uuid): 
            tut_obj, _ = ActeursTutelle.objects.get_or_create(organisation=org_tut)
            MembresTutelle.objects.get_or_create(id_membre=m_uuid, tutelle=tut_obj)
        create_user_group(3000, role_tut, org_tut, "tutelle", ["responsable", "membre", "membre"], link_tut)

        # --- D. SERVICE CONTRACTANT MANAGEMENT ---
        create_user_group(1100, role_sc, org_sc, "sc_boss", ["responsable_service"], None)

        self.stdout.write(self.style.SUCCESS("\nSeeding of test users completed! Password: password123"))
