"""
seed_all.py — Complete seed script for all microservices.

HOW TO RUN (from inside the relevant Docker container):
  # Auth + Organisation service
  docker exec -it <auth_service_container> python manage.py shell < seed_all.py
  # OR copy it in and run: python seed_all.py

The script is split into sections. Run the correct section for each service.
"""

# =============================================================================
# SECTION 1 — AUTH SERVICE  (auth_service DB)
#   Models: Role, Permission, PermissionRole, Utilisateur
#   Prerequisite: roles & permissions already seeded (run_seed() already done)
# =============================================================================

SECTION_1 = """
import uuid
from django.db import transaction
from auth_service.models import Role, Utilisateur

# UUIDs are fixed so the Organisation service can reference them
MEMBRE_UUIDS = {
    # Service Contractants  (SC-1 … SC-5)
    "sc1_resp":   "11000001-0000-0000-0000-000000000001",
    "sc1_red":    "11000001-0000-0000-0000-000000000002",
    "sc2_resp":   "11000002-0000-0000-0000-000000000001",
    "sc2_red":    "11000002-0000-0000-0000-000000000002",
    "sc3_resp":   "11000003-0000-0000-0000-000000000001",
    "sc3_red":    "11000003-0000-0000-0000-000000000002",
    "sc4_resp":   "11000004-0000-0000-0000-000000000001",
    "sc4_red":    "11000004-0000-0000-0000-000000000002",
    "sc5_resp":   "11000005-0000-0000-0000-000000000001",
    "sc5_red":    "11000005-0000-0000-0000-000000000002",
    # Opérateurs Économiques  (OE-1 … OE-5)
    "oe1_resp":   "22000001-0000-0000-0000-000000000001",
    "oe1_prep":   "22000001-0000-0000-0000-000000000002",
    "oe2_resp":   "22000002-0000-0000-0000-000000000001",
    "oe2_prep":   "22000002-0000-0000-0000-000000000002",
    "oe3_resp":   "22000003-0000-0000-0000-000000000001",
    "oe3_prep":   "22000003-0000-0000-0000-000000000002",
    "oe4_resp":   "22000004-0000-0000-0000-000000000001",
    "oe4_prep":   "22000004-0000-0000-0000-000000000002",
    "oe5_resp":   "22000005-0000-0000-0000-000000000001",
    "oe5_prep":   "22000005-0000-0000-0000-000000000002",
    # Commissions Externes  (CE-1 … CE-5)
    "ce1_resp":   "33000001-0000-0000-0000-000000000001",
    "ce1_eval":   "33000001-0000-0000-0000-000000000002",
    "ce2_resp":   "33000002-0000-0000-0000-000000000001",
    "ce2_eval":   "33000002-0000-0000-0000-000000000002",
    "ce3_resp":   "33000003-0000-0000-0000-000000000001",
    "ce3_eval":   "33000003-0000-0000-0000-000000000002",
    "ce4_resp":   "33000004-0000-0000-0000-000000000001",
    "ce4_eval":   "33000004-0000-0000-0000-000000000002",
    "ce5_resp":   "33000005-0000-0000-0000-000000000001",
    "ce5_eval":   "33000005-0000-0000-0000-000000000002",
}

USERS = [
    # --- Service Contractants ---
    # SC-1 : Ministère des Travaux Publics
    {"email": "resp.sc1@mtp.dz",    "password": "Sc1Resp@2025",  "role": "RESP_SC",        "membre_key": "sc1_resp"},
    {"email": "redact.sc1@mtp.dz",  "password": "Sc1Red@2025",   "role": "REDACTEUR_CDC",  "membre_key": "sc1_red"},
    # SC-2 : Direction des Ressources en Eau
    {"email": "resp.sc2@dre.dz",    "password": "Sc2Resp@2025",  "role": "RESP_SC",        "membre_key": "sc2_resp"},
    {"email": "redact.sc2@dre.dz",  "password": "Sc2Red@2025",   "role": "REDACTEUR_CDC",  "membre_key": "sc2_red"},
    # SC-3 : APC Alger Centre
    {"email": "resp.sc3@apc-alger.dz","password": "Sc3Resp@2025","role": "RESP_SC",        "membre_key": "sc3_resp"},
    {"email": "redact.sc3@apc-alger.dz","password":"Sc3Red@2025","role": "REDACTEUR_CDC",  "membre_key": "sc3_red"},
    # SC-4 : Université de Constantine
    {"email": "resp.sc4@univ-const.dz","password":"Sc4Resp@2025","role": "RESP_SC",        "membre_key": "sc4_resp"},
    {"email": "redact.sc4@univ-const.dz","password":"Sc4Red@2025","role": "REDACTEUR_CDC", "membre_key": "sc4_red"},
    # SC-5 : CHU Mustapha Bacha
    {"email": "resp.sc5@chu-mb.dz",  "password": "Sc5Resp@2025", "role": "RESP_SC",        "membre_key": "sc5_resp"},
    {"email": "redact.sc5@chu-mb.dz","password": "Sc5Red@2025",  "role": "REDACTEUR_CDC",  "membre_key": "sc5_red"},

    # --- Opérateurs Économiques ---
    # OE-1 : BatiConstruct SARL
    {"email": "resp.oe1@baticonstruct.dz","password":"Oe1Resp@2025","role": "RESP_OE",    "membre_key": "oe1_resp"},
    {"email": "prep.oe1@baticonstruct.dz","password":"Oe1Prep@2025","role": "PREPARATEUR_OE","membre_key": "oe1_prep"},
    # OE-2 : AquaTech SPA
    {"email": "resp.oe2@aquatech.dz","password":"Oe2Resp@2025",   "role": "RESP_OE",       "membre_key": "oe2_resp"},
    {"email": "prep.oe2@aquatech.dz","password":"Oe2Prep@2025",   "role": "PREPARATEUR_OE","membre_key": "oe2_prep"},
    # OE-3 : InfoSystems EURL
    {"email": "resp.oe3@infosys.dz", "password":"Oe3Resp@2025",   "role": "RESP_OE",       "membre_key": "oe3_resp"},
    {"email": "prep.oe3@infosys.dz", "password":"Oe3Prep@2025",   "role": "PREPARATEUR_OE","membre_key": "oe3_prep"},
    # OE-4 : MediSupply SPA
    {"email": "resp.oe4@medisupply.dz","password":"Oe4Resp@2025", "role": "RESP_OE",       "membre_key": "oe4_resp"},
    {"email": "prep.oe4@medisupply.dz","password":"Oe4Prep@2025", "role": "PREPARATEUR_OE","membre_key": "oe4_prep"},
    # OE-5 : EnerGreen SARL
    {"email": "resp.oe5@energreen.dz","password":"Oe5Resp@2025",  "role": "RESP_OE",       "membre_key": "oe5_resp"},
    {"email": "prep.oe5@energreen.dz","password":"Oe5Prep@2025",  "role": "PREPARATEUR_OE","membre_key": "oe5_prep"},

    # --- Commissions Externes ---
    # CE-1 : Commission Wilaya d'Alger
    {"email": "resp.ce1@cm-alger.dz","password":"Ce1Resp@2025",   "role": "RESP_CM",       "membre_key": "ce1_resp"},
    {"email": "eval.ce1@cm-alger.dz","password":"Ce1Eval@2025",   "role": "EVALUATEUR",    "membre_key": "ce1_eval"},
    # CE-2 : Commission Sectorielle Eau
    {"email": "resp.ce2@cm-eau.dz",  "password":"Ce2Resp@2025",   "role": "RESP_CM",       "membre_key": "ce2_resp"},
    {"email": "eval.ce2@cm-eau.dz",  "password":"Ce2Eval@2025",   "role": "EVALUATEUR",    "membre_key": "ce2_eval"},
    # CE-3 : Commission Nationale Infrastructure
    {"email": "resp.ce3@cm-infra.dz","password":"Ce3Resp@2025",   "role": "RESP_CM",       "membre_key": "ce3_resp"},
    {"email": "eval.ce3@cm-infra.dz","password":"Ce3Eval@2025",   "role": "EVALUATEUR",    "membre_key": "ce3_eval"},
    # CE-4 : Commission Wilaya de Constantine
    {"email": "resp.ce4@cm-const.dz","password":"Ce4Resp@2025",   "role": "RESP_CM",       "membre_key": "ce4_resp"},
    {"email": "eval.ce4@cm-const.dz","password":"Ce4Eval@2025",   "role": "EVALUATEUR",    "membre_key": "ce4_eval"},
    # CE-5 : Commission Sectorielle Santé
    {"email": "resp.ce5@cm-sante.dz","password":"Ce5Resp@2025",   "role": "RESP_CM",       "membre_key": "ce5_resp"},
    {"email": "eval.ce5@cm-sante.dz","password":"Ce5Eval@2025",   "role": "EVALUATEUR",    "membre_key": "ce5_eval"},
]

def seed_users():
    with transaction.atomic():
        created = 0
        for u in USERS:
            role = Role.objects.get(nom_role=u["role"])
            membre_uuid = uuid.UUID(MEMBRE_UUIDS[u["membre_key"]])
            if not Utilisateur.objects.filter(email=u["email"]).exists():
                user = Utilisateur(
                    email=u["email"],
                    id_membre=membre_uuid,
                    id_role=role,
                    is_active=True,
                    must_change_password=False,
                )
                user.set_password(u["password"])
                user.save()
                created += 1
                print(f"  [+] {u['email']}  ({u['role']})")
            else:
                print(f"  [=] Exists: {u['email']}")
        print(f"\\n  Done — {created} users created.")

seed_users()
"""

print(SECTION_1)


# =============================================================================
# SECTION 2 — ORGANISATION SERVICE  (organisation_service DB)
#   Models: Organisation, OperateurEconomique, ServiceContractant,
#           CommissionExterne, Membre
# =============================================================================

SECTION_2 = """
import uuid
from django.db import transaction
from organisation_service.models import (
    Organisation, OperateurEconomique, ServiceContractant,
    CommissionExterne, Membre, TypeEntite, NiveauCompetence,
)

# Must match the UUIDs used in the Auth service seed
MEMBRE_UUIDS = {
    "sc1_resp": uuid.UUID("11000001-0000-0000-0000-000000000001"),
    "sc1_red":  uuid.UUID("11000001-0000-0000-0000-000000000002"),
    "sc2_resp": uuid.UUID("11000002-0000-0000-0000-000000000001"),
    "sc2_red":  uuid.UUID("11000002-0000-0000-0000-000000000002"),
    "sc3_resp": uuid.UUID("11000003-0000-0000-0000-000000000001"),
    "sc3_red":  uuid.UUID("11000003-0000-0000-0000-000000000002"),
    "sc4_resp": uuid.UUID("11000004-0000-0000-0000-000000000001"),
    "sc4_red":  uuid.UUID("11000004-0000-0000-0000-000000000002"),
    "sc5_resp": uuid.UUID("11000005-0000-0000-0000-000000000001"),
    "sc5_red":  uuid.UUID("11000005-0000-0000-0000-000000000002"),
    "oe1_resp": uuid.UUID("22000001-0000-0000-0000-000000000001"),
    "oe1_prep": uuid.UUID("22000001-0000-0000-0000-000000000002"),
    "oe2_resp": uuid.UUID("22000002-0000-0000-0000-000000000001"),
    "oe2_prep": uuid.UUID("22000002-0000-0000-0000-000000000002"),
    "oe3_resp": uuid.UUID("22000003-0000-0000-0000-000000000001"),
    "oe3_prep": uuid.UUID("22000003-0000-0000-0000-000000000002"),
    "oe4_resp": uuid.UUID("22000004-0000-0000-0000-000000000001"),
    "oe4_prep": uuid.UUID("22000004-0000-0000-0000-000000000002"),
    "oe5_resp": uuid.UUID("22000005-0000-0000-0000-000000000001"),
    "oe5_prep": uuid.UUID("22000005-0000-0000-0000-000000000002"),
    "ce1_resp": uuid.UUID("33000001-0000-0000-0000-000000000001"),
    "ce1_eval": uuid.UUID("33000001-0000-0000-0000-000000000002"),
    "ce2_resp": uuid.UUID("33000002-0000-0000-0000-000000000001"),
    "ce2_eval": uuid.UUID("33000002-0000-0000-0000-000000000002"),
    "ce3_resp": uuid.UUID("33000003-0000-0000-0000-000000000001"),
    "ce3_eval": uuid.UUID("33000003-0000-0000-0000-000000000002"),
    "ce4_resp": uuid.UUID("33000004-0000-0000-0000-000000000001"),
    "ce4_eval": uuid.UUID("33000004-0000-0000-0000-000000000002"),
    "ce5_resp": uuid.UUID("33000005-0000-0000-0000-000000000001"),
    "ce5_eval": uuid.UUID("33000005-0000-0000-0000-000000000002"),
}

# Fixed org UUIDs so the Marché service can reference id_service_contractant
SC_ORG_UUIDS = {
    "sc1": uuid.UUID("aaaaaaaa-0001-0000-0000-000000000000"),
    "sc2": uuid.UUID("aaaaaaaa-0002-0000-0000-000000000000"),
    "sc3": uuid.UUID("aaaaaaaa-0003-0000-0000-000000000000"),
    "sc4": uuid.UUID("aaaaaaaa-0004-0000-0000-000000000000"),
    "sc5": uuid.UUID("aaaaaaaa-0005-0000-0000-000000000000"),
}

SERVICE_CONTRACTANTS = [
    {
        "key": "sc1",
        "nom": "Ministère des Travaux Publics",
        "adresse": "Rue des Frères Bouadou, Bir Mourad Raïs, Alger",
        "email": "contact@mtp.gov.dz",
        "wilaya": "Alger",
        "secteur": "Travaux publics",
        "code_service": "MTP-001",
        "secteur_activite": "Infrastructure routière",
        "membres": [
            {"key": "sc1_resp", "nom": "Benali", "prenom": "Rachid",    "telephone": "021-123-001", "fonction": "Responsable SC"},
            {"key": "sc1_red",  "nom": "Khelifi","prenom": "Amina",     "telephone": "021-123-002", "fonction": "Rédacteur CDC"},
        ],
    },
    {
        "key": "sc2",
        "nom": "Direction des Ressources en Eau – Alger",
        "adresse": "Cité des Orangers, Staouéli, Alger",
        "email": "contact@dre-alger.gov.dz",
        "wilaya": "Alger",
        "secteur": "Hydraulique",
        "code_service": "DRE-016",
        "secteur_activite": "Alimentation en eau potable",
        "membres": [
            {"key": "sc2_resp", "nom": "Mebarki", "prenom": "Karim",   "telephone": "021-456-001", "fonction": "Responsable SC"},
            {"key": "sc2_red",  "nom": "Hadj",    "prenom": "Fatima",  "telephone": "021-456-002", "fonction": "Rédacteur CDC"},
        ],
    },
    {
        "key": "sc3",
        "nom": "Commune d'Alger Centre (APC)",
        "adresse": "Place des Martyrs, Alger Centre, Alger",
        "email": "apc@alger-centre.gov.dz",
        "wilaya": "Alger",
        "secteur": "Collectivités locales",
        "code_service": "APC-1601",
        "secteur_activite": "Services municipaux",
        "membres": [
            {"key": "sc3_resp", "nom": "Bouhired", "prenom": "Said",   "telephone": "021-789-001", "fonction": "Responsable SC"},
            {"key": "sc3_red",  "nom": "Ziani",    "prenom": "Nadia",  "telephone": "021-789-002", "fonction": "Rédacteur CDC"},
        ],
    },
    {
        "key": "sc4",
        "nom": "Université des Sciences – Constantine",
        "adresse": "Route Ain El Bey, Constantine",
        "email": "contact@univ-constantine.dz",
        "wilaya": "Constantine",
        "secteur": "Enseignement supérieur",
        "code_service": "UNIV-025",
        "secteur_activite": "Education et recherche",
        "membres": [
            {"key": "sc4_resp", "nom": "Ferhat", "prenom": "Mohamed",  "telephone": "031-321-001", "fonction": "Responsable SC"},
            {"key": "sc4_red",  "nom": "Bouzid", "prenom": "Leila",    "telephone": "031-321-002", "fonction": "Rédacteur CDC"},
        ],
    },
    {
        "key": "sc5",
        "nom": "CHU Mustapha Bacha – Alger",
        "adresse": "Place du 1er Mai, Alger",
        "email": "direction@chu-mustapha.dz",
        "wilaya": "Alger",
        "secteur": "Santé",
        "code_service": "CHU-MBP",
        "secteur_activite": "Santé publique hospitalière",
        "membres": [
            {"key": "sc5_resp", "nom": "Mekki",  "prenom": "Hocine",   "telephone": "021-654-001", "fonction": "Responsable SC"},
            {"key": "sc5_red",  "nom": "Saidi",  "prenom": "Yasmine",  "telephone": "021-654-002", "fonction": "Rédacteur CDC"},
        ],
    },
]

OPERATEURS_ECONOMIQUES = [
    {
        "nom": "BatiConstruct SARL",
        "adresse": "Zone Industrielle, Rouiba, Alger",
        "email": "contact@baticonstruct.dz",
        "wilaya": "Alger",
        "secteur": "BTP",
        "nif": "099820160001234",
        "num_rc": "16/00-1234567B05",
        "membres": [
            {"key": "oe1_resp", "nom": "Djaafri", "prenom": "Omar",    "telephone": "0550-100-001", "fonction": "Directeur Général"},
            {"key": "oe1_prep", "nom": "Lakehal", "prenom": "Sara",    "telephone": "0550-100-002", "fonction": "Préparateur offres"},
        ],
    },
    {
        "nom": "AquaTech SPA",
        "adresse": "Lotissement El Feth, Chéraga, Alger",
        "email": "contact@aquatech.dz",
        "wilaya": "Alger",
        "secteur": "Hydraulique",
        "nif": "099820160005678",
        "num_rc": "16/00-2345678B05",
        "membres": [
            {"key": "oe2_resp", "nom": "Boudissa","prenom": "Tahar",   "telephone": "0551-200-001", "fonction": "PDG"},
            {"key": "oe2_prep", "nom": "Chiali",  "prenom": "Meriem",  "telephone": "0551-200-002", "fonction": "Chargée des offres"},
        ],
    },
    {
        "nom": "InfoSystems EURL",
        "adresse": "Technopôle Sidi Abdellah, Zeralda, Alger",
        "email": "contact@infosystems.dz",
        "wilaya": "Alger",
        "secteur": "Informatique",
        "nif": "099820160009012",
        "num_rc": "16/00-3456789B05",
        "membres": [
            {"key": "oe3_resp", "nom": "Hamidi",  "prenom": "Yacine",  "telephone": "0552-300-001", "fonction": "Gérant"},
            {"key": "oe3_prep", "nom": "Benzerga","prenom": "Imane",   "telephone": "0552-300-002", "fonction": "Technicienne offres"},
        ],
    },
    {
        "nom": "MediSupply SPA",
        "adresse": "Rue Didouche Mourad, Alger",
        "email": "contact@medisupply.dz",
        "wilaya": "Alger",
        "secteur": "Fournitures médicales",
        "nif": "099820160003456",
        "num_rc": "16/00-4567890B05",
        "membres": [
            {"key": "oe4_resp", "nom": "Ouali",   "prenom": "Djamel",  "telephone": "0553-400-001", "fonction": "Directeur commercial"},
            {"key": "oe4_prep", "nom": "Kaidi",   "prenom": "Rania",   "telephone": "0553-400-002", "fonction": "Assistante offres"},
        ],
    },
    {
        "nom": "EnerGreen SARL",
        "adresse": "Zone d'Activités, Oran",
        "email": "contact@energreen.dz",
        "wilaya": "Oran",
        "secteur": "Énergies renouvelables",
        "nif": "099820310007890",
        "num_rc": "31/00-5678901B05",
        "membres": [
            {"key": "oe5_resp", "nom": "Taleb",   "prenom": "Bilal",   "telephone": "0554-500-001", "fonction": "PDG"},
            {"key": "oe5_prep", "nom": "Messaoud","prenom": "Dounia",  "telephone": "0554-500-002", "fonction": "Responsable soumissions"},
        ],
    },
]

COMMISSIONS_EXTERNES = [
    {
        "nom": "Commission des Marchés – Wilaya d'Alger",
        "adresse": "Palais du Gouvernement, Place Amilcar Cabral, Alger",
        "email": "cm@wilaya-alger.gov.dz",
        "wilaya": "Alger",
        "secteur": "Administration publique",
        "num_agrement": "AGR-CMA-016",
        "specialite": "Travaux et services publics",
        "niveau": NiveauCompetence.WILAYA,
        "seuil": 50_000_000.00,
        "membres": [
            {"key": "ce1_resp", "nom": "Benhaddou","prenom": "Abdelmalek","telephone":"021-001-001","fonction": "Président Commission"},
            {"key": "ce1_eval", "nom": "Aissaoui", "prenom": "Houria",    "telephone":"021-001-002","fonction": "Évaluateur"},
        ],
    },
    {
        "nom": "Commission Sectorielle – Eau et Assainissement",
        "adresse": "Ministère des Ressources en Eau, Alger",
        "email": "cm@mre.gov.dz",
        "wilaya": "Alger",
        "secteur": "Hydraulique",
        "num_agrement": "AGR-CMH-SEC",
        "specialite": "Hydraulique et assainissement",
        "niveau": NiveauCompetence.SECTORIELLE,
        "seuil": 200_000_000.00,
        "membres": [
            {"key": "ce2_resp", "nom": "Rezig",   "prenom": "Farid",    "telephone":"021-002-001","fonction": "Président Commission"},
            {"key": "ce2_eval", "nom": "Ghouli",  "prenom": "Samira",   "telephone":"021-002-002","fonction": "Évaluatrice"},
        ],
    },
    {
        "nom": "Commission Nationale – Infrastructure",
        "adresse": "Ministère des Travaux Publics, Alger",
        "email": "cm-infra@mtp.gov.dz",
        "wilaya": "Alger",
        "secteur": "Travaux publics",
        "num_agrement": "AGR-CMN-INFRA",
        "specialite": "Infrastructure et génie civil",
        "niveau": NiveauCompetence.NATIONAL,
        "seuil": 1_000_000_000.00,
        "membres": [
            {"key": "ce3_resp", "nom": "Haddag",  "prenom": "Nacer",    "telephone":"021-003-001","fonction": "Président Commission"},
            {"key": "ce3_eval", "nom": "Bougrine","prenom": "Lynda",    "telephone":"021-003-002","fonction": "Évaluatrice"},
        ],
    },
    {
        "nom": "Commission des Marchés – Wilaya de Constantine",
        "adresse": "Palais de la Wilaya, Constantine",
        "email": "cm@wilaya-constantine.gov.dz",
        "wilaya": "Constantine",
        "secteur": "Administration publique",
        "num_agrement": "AGR-CMC-025",
        "specialite": "Enseignement et équipements publics",
        "niveau": NiveauCompetence.WILAYA,
        "seuil": 50_000_000.00,
        "membres": [
            {"key": "ce4_resp", "nom": "Benkhelifa","prenom":"Mustapha","telephone":"031-004-001","fonction": "Président Commission"},
            {"key": "ce4_eval", "nom": "Kessal",   "prenom": "Assia",   "telephone":"031-004-002","fonction": "Évaluatrice"},
        ],
    },
    {
        "nom": "Commission Sectorielle – Santé Publique",
        "adresse": "Ministère de la Santé, Alger",
        "email": "cm@sante.gov.dz",
        "wilaya": "Alger",
        "secteur": "Santé",
        "num_agrement": "AGR-CMS-SAN",
        "specialite": "Equipements et fournitures médicales",
        "niveau": NiveauCompetence.SECTORIELLE,
        "seuil": 300_000_000.00,
        "membres": [
            {"key": "ce5_resp", "nom": "Touati",  "prenom": "Reda",     "telephone":"021-005-001","fonction": "Président Commission"},
            {"key": "ce5_eval", "nom": "Boucif",  "prenom": "Kahina",   "telephone":"021-005-002","fonction": "Évaluatrice"},
        ],
    },
]

def seed_organisations():
    with transaction.atomic():
        # ---- Service Contractants ----
        print("\\n=== Service Contractants ===")
        for sc_data in SERVICE_CONTRACTANTS:
            org_uuid = SC_ORG_UUIDS[sc_data["key"]]
            org, created = Organisation.objects.get_or_create(
                id_organisation=org_uuid,
                defaults={
                    "nom_officiel": sc_data["nom"],
                    "adresse_siege": sc_data["adresse"],
                    "email_contact": sc_data["email"],
                    "type_entite": TypeEntite.SERVICE_CONTRACTANT,
                    "wilaya": sc_data["wilaya"],
                    "secteur": sc_data["secteur"],
                },
            )
            tag = "[+]" if created else "[=]"
            print(f"  {tag} Organisation : {org.nom_officiel}")

            ServiceContractant.objects.get_or_create(
                organisation=org,
                defaults={
                    "code_service": sc_data["code_service"],
                    "secteur_activite": sc_data["secteur_activite"],
                },
            )

            for m in sc_data["membres"]:
                Membre.objects.get_or_create(
                    id_membre=MEMBRE_UUIDS[m["key"]],
                    defaults={
                        "organisation": org,
                        "nom": m["nom"],
                        "prenom": m["prenom"],
                        "telephone": m["telephone"],
                        "fonction": m["fonction"],
                    },
                )
                print(f"      membre : {m['prenom']} {m['nom']}  ({m['fonction']})")

        # ---- Opérateurs Économiques ----
        print("\\n=== Opérateurs Économiques ===")
        for oe_data in OPERATEURS_ECONOMIQUES:
            org = Organisation.objects.create(
                nom_officiel=oe_data["nom"],
                adresse_siege=oe_data["adresse"],
                email_contact=oe_data["email"],
                type_entite=TypeEntite.OPERATEUR_ECONOMIQUE,
                wilaya=oe_data["wilaya"],
                secteur=oe_data["secteur"],
            )
            print(f"  [+] Organisation : {org.nom_officiel}")

            OperateurEconomique.objects.create(
                organisation=org,
                nif=oe_data["nif"],
                num_registre_commerce=oe_data["num_rc"],
            )

            for m in oe_data["membres"]:
                Membre.objects.get_or_create(
                    id_membre=MEMBRE_UUIDS[m["key"]],
                    defaults={
                        "organisation": org,
                        "nom": m["nom"],
                        "prenom": m["prenom"],
                        "telephone": m["telephone"],
                        "fonction": m["fonction"],
                    },
                )
                print(f"      membre : {m['prenom']} {m['nom']}  ({m['fonction']})")

        # ---- Commissions Externes ----
        print("\\n=== Commissions Externes ===")
        for ce_data in COMMISSIONS_EXTERNES:
            org = Organisation.objects.create(
                nom_officiel=ce_data["nom"],
                adresse_siege=ce_data["adresse"],
                email_contact=ce_data["email"],
                type_entite=TypeEntite.COMMISSION_EXTERNE,
                wilaya=ce_data["wilaya"],
                secteur=ce_data["secteur"],
            )
            print(f"  [+] Organisation : {org.nom_officiel}")

            CommissionExterne.objects.create(
                organisation=org,
                numero_agrement=ce_data["num_agrement"],
                specialite=ce_data["specialite"],
                niveau_competence=ce_data["niveau"],
                seuil=ce_data["seuil"],
            )

            for m in ce_data["membres"]:
                Membre.objects.get_or_create(
                    id_membre=MEMBRE_UUIDS[m["key"]],
                    defaults={
                        "organisation": org,
                        "nom": m["nom"],
                        "prenom": m["prenom"],
                        "telephone": m["telephone"],
                        "fonction": m["fonction"],
                    },
                )
                print(f"      membre : {m['prenom']} {m['nom']}  ({m['fonction']})")

        print("\\n=== ORGANISATION SEED TERMINÉ ===")

seed_organisations()
"""

print(SECTION_2)


# =============================================================================
# SECTION 3 — MARCHÉ SERVICE  (marche_service DB)
#   Models: AppelOffres, DocumentsAppel
#   One AppelOffres of type "publique" per Service Contractant
#   id_service_contractant = the integer PK Django auto-assigns to
#   the ServiceContractant row.  Since we use fixed org UUIDs and
#   ServiceContractant.pk == Organisation.pk (OneToOne), we look them up
#   via Organisation UUID.
# =============================================================================

SECTION_3 = """
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from marche_service.models import AppelOffres

# Fixed SC org UUIDs (same as Section 2)
SC_ORG_UUIDS = [
    uuid.UUID("aaaaaaaa-0001-0000-0000-000000000000"),
    uuid.UUID("aaaaaaaa-0002-0000-0000-000000000000"),
    uuid.UUID("aaaaaaaa-0003-0000-0000-000000000000"),
    uuid.UUID("aaaaaaaa-0004-0000-0000-000000000000"),
    uuid.UUID("aaaaaaaa-0005-0000-0000-000000000000"),
]

# Retrieve the integer PKs from the Organisation service DB
# (both services share a cross-service concept; id_service_contractant
# is an IntegerField referencing the pk of ServiceContractant)
# If Organisation service is a separate DB, replace with hard-coded integers
# after running Section 2 and noting the assigned PKs.

try:
    from organisation_service.models import Organisation
    SC_INT_IDS = [
        Organisation.objects.get(id_organisation=uid).pk   # pk is int-like via UUID
        for uid in SC_ORG_UUIDS
    ]
except Exception:
    # Fallback: hard-code after running Section 2
    SC_INT_IDS = [1, 2, 3, 4, 5]   # replace with actual PKs if needed

now = timezone.now()

APPELS_OFFRES = [
    {
        "id_service_contractant": SC_INT_IDS[0],
        "reference": "MTP-AO-2025-001",
        "titre": "Réhabilitation de la RN1 – Section Alger / Blida",
        "description": (
            "Travaux de réhabilitation et de renforcement de la chaussée sur "
            "un linéaire de 28 km, incluant la signalisation horizontale et verticale."
        ),
        "type_procedure": "publique",
        "type_prestation": "travaux",
        "visibilite": "public",
        "wilaya": "Alger",
        "secteur": "Travaux publics",
        "localisation": "Route Nationale N°1 – PK 0 à PK 28",
        "montant_estime": Decimal("850000000.00"),
        "date_publication": now,
        "date_limite_soumission": now + timedelta(days=45),
        "date_ouverture_plis": now + timedelta(days=46),
        "poids_technique": 40,
        "poids_financier": 60,
        "seuil_technique": 70,
        "methodology": "weighted",
        "statut": "valide",
        "etat_execution": "publie",
        "validation_level": "externe_wilaya",
        "required_docs_admin": ["extrait_casier", "certificat_fiscal", "rc"],
        "required_docs_tech": ["memoire_technique", "references_similaires"],
        "required_docs_fin": ["bilan_3ans", "lettre_soumission"],
        "minimum_revenue_da": 500_000_000,
        "minimum_experience_years": 5,
    },
    {
        "id_service_contractant": SC_INT_IDS[1],
        "reference": "DRE-AO-2025-001",
        "titre": "Construction d'un château d'eau de 2 000 m³ – Commune de Douéra",
        "description": (
            "Conception et construction d'un réservoir de stockage d'eau potable "
            "d'une capacité de 2 000 m³, avec les ouvrages de génie civil associés."
        ),
        "type_procedure": "publique",
        "type_prestation": "travaux",
        "visibilite": "public",
        "wilaya": "Alger",
        "secteur": "Hydraulique",
        "localisation": "Commune de Douéra, wilaya d'Alger",
        "montant_estime": Decimal("320000000.00"),
        "date_publication": now,
        "date_limite_soumission": now + timedelta(days=40),
        "date_ouverture_plis": now + timedelta(days=41),
        "poids_technique": 50,
        "poids_financier": 50,
        "seuil_technique": 65,
        "methodology": "weighted",
        "statut": "valide",
        "etat_execution": "publie",
        "validation_level": "externe_secteur",
        "required_docs_admin": ["extrait_casier", "certificat_fiscal", "rc", "attestation_cnas"],
        "required_docs_tech": ["plan_execution", "references_hydrauliques"],
        "required_docs_fin": ["bilan_3ans", "lettre_soumission", "cautionnement"],
        "minimum_revenue_da": 200_000_000,
        "minimum_experience_years": 3,
    },
    {
        "id_service_contractant": SC_INT_IDS[2],
        "reference": "APC-AC-AO-2025-001",
        "titre": "Fourniture et pose de luminaires LED – Alger Centre",
        "description": (
            "Remplacement de l'éclairage public par des luminaires à LED haute efficacité "
            "sur 150 rues du centre-ville d'Alger, incluant la mise en service et la GMAO."
        ),
        "type_procedure": "publique",
        "type_prestation": "fournitures",
        "visibilite": "public",
        "wilaya": "Alger",
        "secteur": "Collectivités locales",
        "localisation": "Commune d'Alger Centre",
        "montant_estime": Decimal("95000000.00"),
        "date_publication": now,
        "date_limite_soumission": now + timedelta(days=30),
        "date_ouverture_plis": now + timedelta(days=31),
        "poids_technique": 30,
        "poids_financier": 70,
        "seuil_technique": 60,
        "methodology": "weighted",
        "statut": "valide",
        "etat_execution": "publie",
        "validation_level": "interne",
        "required_docs_admin": ["extrait_casier", "rc", "nif"],
        "required_docs_tech": ["fiche_technique_produit", "certificat_conformite"],
        "required_docs_fin": ["devis_quantitatif", "lettre_soumission"],
        "minimum_revenue_da": 50_000_000,
        "minimum_experience_years": 2,
    },
    {
        "id_service_contractant": SC_INT_IDS[3],
        "reference": "UNIV-CST-AO-2025-001",
        "titre": "Acquisition d'équipements informatiques – Université Constantine",
        "description": (
            "Fourniture, installation et configuration de 300 postes de travail, "
            "20 serveurs rack et l'infrastructure réseau du campus principal."
        ),
        "type_procedure": "publique",
        "type_prestation": "fournitures",
        "visibilite": "public",
        "wilaya": "Constantine",
        "secteur": "Enseignement supérieur",
        "localisation": "Campus principal – Route Ain El Bey, Constantine",
        "montant_estime": Decimal("180000000.00"),
        "date_publication": now,
        "date_limite_soumission": now + timedelta(days=35),
        "date_ouverture_plis": now + timedelta(days=36),
        "poids_technique": 60,
        "poids_financier": 40,
        "seuil_technique": 75,
        "methodology": "weighted",
        "statut": "valide",
        "etat_execution": "publie",
        "validation_level": "externe_wilaya",
        "required_docs_admin": ["extrait_casier", "rc", "certificat_fiscal"],
        "required_docs_tech": ["fiche_technique", "certifications_produits", "references_similaires"],
        "required_docs_fin": ["bilan_3ans", "lettre_soumission"],
        "minimum_revenue_da": 100_000_000,
        "minimum_experience_years": 3,
    },
    {
        "id_service_contractant": SC_INT_IDS[4],
        "reference": "CHU-MB-AO-2025-001",
        "titre": "Acquisition de consommables médicaux – CHU Mustapha Bacha",
        "description": (
            "Fourniture de consommables médicaux à usage unique (seringues, gants, "
            "compresses, sondes, perfuseurs) pour une durée contractuelle de 12 mois."
        ),
        "type_procedure": "publique",
        "type_prestation": "fournitures",
        "visibilite": "public",
        "wilaya": "Alger",
        "secteur": "Santé",
        "localisation": "CHU Mustapha Bacha – Place du 1er Mai, Alger",
        "montant_estime": Decimal("65000000.00"),
        "date_publication": now,
        "date_limite_soumission": now + timedelta(days=30),
        "date_ouverture_plis": now + timedelta(days=31),
        "poids_technique": 50,
        "poids_financier": 50,
        "seuil_technique": 70,
        "methodology": "weighted",
        "statut": "valide",
        "etat_execution": "publie",
        "validation_level": "externe_secteur",
        "required_docs_admin": ["rc", "nif", "certificat_fiscal", "attestation_cnas"],
        "required_docs_tech": ["certificat_conformite_ce", "fiche_technique_lot"],
        "required_docs_fin": ["bilan_3ans", "lettre_soumission", "cautionnement"],
        "minimum_revenue_da": 30_000_000,
        "minimum_experience_years": 2,
    },
]

def seed_appels_offres():
    with transaction.atomic():
        print("\\n=== Appels d'Offres ===")
        for ao_data in APPELS_OFFRES:
            ao, created = AppelOffres.objects.get_or_create(
                reference=ao_data["reference"],
                defaults=ao_data,
            )
            tag = "[+]" if created else "[=]"
            print(f"  {tag} {ao.reference} — {ao.titre[:60]}")
        print(f"\\n  Total AppelOffres : {AppelOffres.objects.count()}")

seed_appels_offres()
"""

print(SECTION_3)