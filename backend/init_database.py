#!/usr/bin/env python3
import os
import sys
import uuid
import hashlib
import random
import json
from datetime import datetime, timedelta, timezone

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit(
        "psycopg2 is required. Install it with:\n"
        "  pip install psycopg2-binary"
    )

# ── connection settings ──────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5433")
DB_NAME     = os.getenv("DB_NAME", "almizan_db")
DB_USER     = os.getenv("DB_USER", "almizan_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "almizan_password")

# ── helpers ──────────────────────────────────────────────────────────
now = datetime.now(timezone.utc)

def ts(offset_days=0, offset_hours=0):
    return (now + timedelta(days=offset_days, hours=offset_hours)).isoformat()

def rand_uuid():
    return str(uuid.uuid4())

def rand_hash():
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()

WILAYAS = [
    "Alger", "Oran", "Constantine", "Annaba", "Blida",
    "Sétif", "Tlemcen", "Batna", "Béjaïa", "Tizi Ouzou",
]
PRENOMS = ["Ahmed", "Fatima", "Yacine", "Amina", "Mohamed", "Sara", "Karim", "Nadia", "Omar", "Leila"]
NOMS    = ["Benaissa", "Khelifi", "Boudiaf", "Mebarki", "Hadj", "Saidi", "Bouzid", "Ferhat", "Amrani", "Belkacem"]


def main():
    print(f"Connecting to postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    conn = psycopg2.connect(
        host=DB_HOST, port=int(DB_PORT),
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ============================================================
        # 1. AUTH SERVICE
        # ============================================================
        print("Seeding: role")
        roles = [
            "service_contractant", "operateur_economique",
            "commission_externe", "tutelle", "admin",
        ]
        for r in roles:
            cur.execute(
                "INSERT INTO role (nom_role) VALUES (%s) ON CONFLICT (nom_role) DO NOTHING",
                (r,),
            )

        cur.execute("SELECT id_role, nom_role FROM role")
        role_map = {row[1]: row[0] for row in cur.fetchall()}

        print("Seeding: permission")
        ROLE_PERMISSIONS = {
            "service_contractant": [
                "responsable_service_contratant", "redacteur_cdc",
                "evaluer_offre_technique", "evaluer_offre_financiere",
                "evaluer_offre_administrative", "valider_offre_intern",
            ],
            "operateur_economique": [
                "responsable_operateur_economique", "soumitter_offre", "faire_recours",
            ],
            "commission_externe": [
                "responsable_commission_externe", "valider_offre_extern",
            ],
            "tutelle": [
                "responsable_tutelle", "valider_offre_tutelle",
            ],
            "admin": ["acces_total"],
        }

        all_perms = set(p for perms in ROLE_PERMISSIONS.values() for p in perms)
        for p in all_perms:
            cur.execute(
                "INSERT INTO permission (nom_permission) VALUES (%s) ON CONFLICT (nom_permission) DO NOTHING",
                (p,),
            )

        cur.execute("SELECT id_permission, nom_permission FROM permission")
        perm_map = {row[1]: row[0] for row in cur.fetchall()}

        print("Seeding: Permission_role")
        for role_name, perms in ROLE_PERMISSIONS.items():
            id_role = role_map.get(role_name)
            if not id_role:
                continue
            for perm_name in perms:
                id_perm = perm_map.get(perm_name)
                if not id_perm:
                    continue
                cur.execute(
                    """INSERT INTO "Permission_role" (id_role, id_permission)
                       VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                    (id_role, id_perm),
                )

        role_ids = list(role_map.values())

        print("Seeding: utilisateurs")
        user_ids = []
        for i in range(10):
            email = f"user{i+1}@almizan.dz"
            pwd_hash = f"pbkdf2_sha256$390000$salt${rand_hash()}"
            cur.execute(
                """INSERT INTO utilisateurs (id_role, id_membre, email, password_hash, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, true, %s, %s)
                   ON CONFLICT (email) DO UPDATE SET updated_at = EXCLUDED.updated_at
                   RETURNING id_utilisateur""",
                (role_ids[i % len(role_ids)], i + 1, email, pwd_hash, ts(-30 + i), ts()),
            )
            user_ids.append(cur.fetchone()[0])

        # ============================================================
        # 2. ACTEURS SERVICE
        # ============================================================
        print("Seeding: organisation")
        org_ids = []
        org_types = ["OPERATEUR_ECONOMIQUE", "SERVICE_CONTRACTANT", "COMMISSION_EXTERNE", "TUTELLE"]
        org_names = [
            "SARL TechBuild", "EURL InfoSys", "SPA GreenEnergy",
            "EPIC Construction", "SARL DataServ", "EURL MedSupply",
            "SPA TransLog", "Ministère des Finances", "Wilaya d'Alger",
            "Commission Nationale des Marchés",
        ]
        for i in range(10):
            oid = rand_uuid()
            org_ids.append(oid)
            cur.execute(
                """INSERT INTO organisation (id_organisation, nom_officiel, adresse_siege, email_contact, type_entite, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id_organisation) DO NOTHING""",
                (
                    oid, org_names[i],
                    f"{random.randint(1,200)} Rue {WILAYAS[i]}, {WILAYAS[i]}",
                    f"contact{i+1}@{org_names[i].split()[1].lower()}.dz",
                    org_types[i % len(org_types)],
                    ts(-60 + i),
                ),
            )

        print("Seeding: acteurs_service_demandeoperateur")
        demande_ids = []
        for i in range(10):
            did = rand_uuid()
            demande_ids.append(did)
            cur.execute(
                """INSERT INTO acteurs_service_demandeoperateur
                   (id, nom_organisation, email_contact, telephone, nif, num_registre_commerce, statut, motif_rejet, cree_le, mis_a_jour_le)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (
                    did, f"Entreprise Demande {i+1}", f"demande{i+1}@example.dz",
                    f"05{random.randint(10000000,99999999)}",
                    f"{random.randint(100000000000000,999999999999999)}",
                    f"RC-{random.randint(10000,99999)}",
                    random.choice(["EN_ATTENTE", "APPROUVE", "REJETE"]),
                    "" if i % 3 != 2 else "Dossier incomplet",
                    ts(-20 + i), ts(),
                ),
            )

        print("Seeding: acteurs_service_demandedocument")
        doc_types_demande = ["REGISTRE_COMMERCE", "NIF", "CNAS_CASNOS", "NON_FAILLITE"]
        for i in range(10):
            cur.execute(
                """INSERT INTO acteurs_service_demandedocument
                   (id, demande_id, document_id, type_document)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (rand_uuid(), demande_ids[i % len(demande_ids)], i + 1, doc_types_demande[i % len(doc_types_demande)]),
            )

        print("Seeding: acteurs_service_operateureconomique")
        for i in range(3):
            cur.execute(
                """INSERT INTO acteurs_service_operateureconomique (organisation_id, nif, num_registre_commerce)
                   VALUES (%s,%s,%s) ON CONFLICT (organisation_id) DO NOTHING""",
                (org_ids[i], f"{random.randint(100000000000000,999999999999999)}", f"RC-{random.randint(10000,99999)}"),
            )

        print("Seeding: acteurs_service_servicecontractant")
        for i in range(3, 6):
            cur.execute(
                """INSERT INTO acteurs_service_servicecontractant (organisation_id, code_service, secteur_activite)
                   VALUES (%s,%s,%s) ON CONFLICT (organisation_id) DO NOTHING""",
                (org_ids[i], f"SC-{random.randint(100,999)}", random.choice(["BTP", "IT", "Santé"])),
            )

        print("Seeding: acteurs_service_commissionexterne")
        for i in range(6, 8):
            cur.execute(
                """INSERT INTO acteurs_service_commissionexterne (organisation_id, numero_agrement, specialite)
                   VALUES (%s,%s,%s) ON CONFLICT (organisation_id) DO NOTHING""",
                (org_ids[i], f"AGR-{random.randint(100,999)}", random.choice(["Générale", "Technique", "Financière"])),
            )

        print("Seeding: acteurs_service_tutelle")
        for i in range(8, 10):
            cur.execute(
                """INSERT INTO acteurs_service_tutelle (organisation_id, ministere_attache)
                   VALUES (%s,%s) ON CONFLICT (organisation_id) DO NOTHING""",
                (org_ids[i], random.choice(["Ministère des Finances", "Ministère de l'Intérieur", "Ministère de la Défense"])),
            )

        # -- contractant_service_commissionexterne seedée AVANT membre (nécessaire pour Membres_Commission_Externe)
        print("Seeding: contractant_service_commissionexterne")
        niveaux = ["Communale", "de Wilaya", "Sectorielle", "Nationale"]
        ce_externe_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO contractant_service_commissionexterne (nom_comission, niveau_competance, seuils_competence_financiere)
                   VALUES (%s,%s,%s)
                   RETURNING id_comission_externe""",
                (
                    f"Commission Externe {i+1}",
                    niveaux[i % len(niveaux)],
                    f"{random.randint(1,50)} milliards DA",
                ),
            )
            ce_externe_ids.append(cur.fetchone()[0])

        # -- membre
        print("Seeding: membre")
        membre_ids = []
        for i in range(10):
            mid = rand_uuid()
            membre_ids.append(mid)
            cur.execute(
                """INSERT INTO membre (id_membre, organisation_id, nom, prenom, telephone, fonction, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id_membre) DO NOTHING""",
                (
                    mid, org_ids[i % len(org_ids)],
                    NOMS[i], PRENOMS[i],
                    f"06{random.randint(10000000,99999999)}",
                    random.choice(["Directeur", "Employé", "Responsable", "Ingénieur", "Comptable"]),
                    ts(-30 + i), ts(),
                ),
            )

        # -- Membres_Tutelle (org_ids[8] et [9] sont les 2 tutelles)
        print("Seeding: Membres_Tutelle")
        tutelle_org_ids = [org_ids[8], org_ids[9]]
        for i in range(10):
            cur.execute(
                """INSERT INTO "Membres_Tutelle" (id_membre, tutelle_id)
                   VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (membre_ids[i % len(membre_ids)], tutelle_org_ids[i % len(tutelle_org_ids)]),
            )

        # -- Membres_Commission_Externe
        print("Seeding: Membres_Commission_Externe")
        for i in range(10):
            cur.execute(
                """INSERT INTO "Membres_Commission_Externe" (id_membre, id_comission_externe)
                   VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (i + 1, ce_externe_ids[i % len(ce_externe_ids)]),
            )

        # ============================================================
        # 3. CONTRACTANT SERVICE
        # ============================================================
        print("Seeding: Services_Contractants")
        sc_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO "Services_Contractants" (id_tutelle, categorie, code_ordonnateur)
                   VALUES (%s,%s,%s) RETURNING id_service""",
                (i + 1, random.choice(["Ministère", "Direction", "Établissement"]), f"ORD-{random.randint(1000,9999)}"),
            )
            sc_ids.append(cur.fetchone()[0])

        print("Seeding: Comission_evaluation (contractant)")
        ce_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO "Comission_evaluation" (id_service, nom_comission, categorie)
                   VALUES (%s,%s,%s) RETURNING id_comission""",
                (sc_ids[i % len(sc_ids)], f"Commission Éval {i+1}", random.choice(["Technique", "Financière", "Administrative"])),
            )
            ce_ids.append(cur.fetchone()[0])

        print("Seeding: Comission_interne")
        ci_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO "Comission_interne" (id_service, nom_comission, type_comission)
                   VALUES (%s,%s,%s) RETURNING id_comission_interne""",
                (sc_ids[i % len(sc_ids)], f"Commission Interne {i+1}", random.choice(["parmanante", "adhoc"])),
            )
            ci_ids.append(cur.fetchone()[0])

        print("Seeding: Membres_Commission_evaluation")
        for i in range(10):
            cur.execute(
                """INSERT INTO "Membres_Commission_evaluation" (id_membre, id_comission)
                   VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                (i + 1, ce_ids[i % len(ce_ids)]),
            )

        print("Seeding: Membres_Commission_interne")
        for i in range(10):
            cur.execute(
                """INSERT INTO "Membres_Commission_interne" (id_membre, id_commision_interne)
                   VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                (i + 1, ci_ids[i % len(ci_ids)]),
            )

        # ============================================================
        # 4. DOCUMENTS SERVICE
        # ============================================================
        print("Seeding: documents")
        doc_ids = []
        related_types = ["appel_offre", "soumission", "contrat", "recours", "demande"]
        for i in range(10):
            cur.execute(
                """INSERT INTO documents
                   (related_type, id_operateur_economique, nom, type_document, storage_url, hash_sha256,
                    taille_fichier, is_encrypted, ia_verif_statut, ia_verif_details, uploaded_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id_document""",
                (
                    related_types[i % len(related_types)], i + 1,
                    f"document_{i+1}.pdf", "application/pdf",
                    f"{rand_uuid()}.pdf", rand_hash(),
                    random.randint(50000, 5000000), False,
                    random.choice(["PENDING", "VALID", "ANOMALY"]),
                    f"Vérification IA #{i+1}", ts(-10 + i),
                ),
            )
            doc_ids.append(cur.fetchone()[0])

        # ============================================================
        # 5. APPELS D'OFFRES SERVICE
        # ============================================================
        print("Seeding: appels_offres")
        appel_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO appels_offres
                   (id_service_contractant, reference, titre, description,
                    type_procedure, type_prestation, wilaya, localisation,
                    montant_estime, date_publication, date_limite_soumission,
                    date_ouverture_plis, poids_technique, poids_financier,
                    statut, created_at, updated_at,
                    minimum_experience_years, minimum_revenue_da,
                    participation_conditions, qualification_category,
                    required_docs_admin, required_docs_fin, required_docs_tech,
                    visibilite)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id_appel_offres""",
                (
                    sc_ids[i % len(sc_ids)],
                    f"AO-2025-{1000+i}",
                    f"Appel d'offres #{i+1} – {random.choice(['Travaux', 'Fournitures', 'Services'])}",
                    f"Description détaillée de l'appel d'offres #{i+1}",
                    random.choice(["ouvert", "restreint", "gre_a_gre"]),
                    random.choice(["fournitures", "services", "travaux"]),
                    WILAYAS[i], f"Zone industrielle, {WILAYAS[i]}",
                    round(random.uniform(1000000, 50000000), 2),
                    ts(-15 + i), ts(15 + i), ts(16 + i),
                    random.randint(30, 70), random.randint(30, 70),
                    random.choice(["brouillon", "publie", "depot_cloture", "attribue"]),
                    ts(-15 + i), ts(),
                    random.randint(0, 10),
                    random.randint(0, 10000000),
                    json.dumps(["condition_1", "condition_2"]),
                    random.choice(["", "Catégorie 1", "Catégorie 2"]),
                    json.dumps(["extrait_role", "bilan"]),
                    json.dumps(["bilan_financier"]),
                    json.dumps(["fiche_technique"]),
                    random.choice(["public", "prive"]),
                ),
            )
            appel_ids.append(cur.fetchone()[0])

        print("Seeding: documents_appel")
        for i in range(10):
            cur.execute(
                """INSERT INTO documents_appel (id_document, id_appel_offres)
                   VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                (doc_ids[i % len(doc_ids)], appel_ids[i % len(appel_ids)]),
            )

        print("Seeding: appels_offres_operateurs_invites")
        for i in range(10):
            cur.execute(
                """INSERT INTO appels_offres_operateurs_invites
                   (id_appel_offres, id_operateur_economique, statut_invitation, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (appel_ids[i % len(appel_ids)], i + 1, random.choice(["invite", "a_repondu", "retire"]), ts(-10 + i), ts()),
            )

        print("Seeding: achats_simples")
        for i in range(10):
            cur.execute(
                """INSERT INTO achats_simples
                   (id_service_contractant, reference, objet, description,
                    type_prestation, wilaya, localisation, montant_estime,
                    id_operateur_economique, statut, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    sc_ids[i % len(sc_ids)], f"AS-2025-{2000+i}",
                    f"Achat simple #{i+1} – {random.choice(['Mobilier', 'Matériel IT', 'Fournitures bureau'])}",
                    f"Achat direct #{i+1}",
                    random.choice(["fournitures", "services", "travaux"]),
                    WILAYAS[i], f"Centre-ville, {WILAYAS[i]}",
                    round(random.uniform(100000, 999999), 2),
                    i + 1, random.choice(["brouillon", "valide", "engage", "annule"]),
                    ts(-5 + i), ts(),
                ),
            )

        print("Seeding: appels_offres_suivis")
        for i in range(10):
            cur.execute(
                """INSERT INTO appels_offres_suivis (id_appel_offres, id_utilisateur, created_at)
                   VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
                (appel_ids[i % len(appel_ids)], user_ids[i % len(user_ids)], ts(-5 + i)),
            )

        # ============================================================
        # 6. SOUMISSIONS
        # ============================================================
        print("Seeding: soumissions")
        soumission_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO soumissions
                   (id_appel_offre, id_soumissionnaire, offre_financiere_chiffree_url,
                    cle_dechiffrement_hash, document_ids, statut, montant_financier,
                    date_soumission, conformite_statut, conformite_rapport)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id_soumission""",
                (
                    appel_ids[i % len(appel_ids)], i + 1,
                    f"https://minio.local/almizan-documents/{rand_uuid()}.pdf",
                    rand_hash(), json.dumps([doc_ids[i % len(doc_ids)]]),
                    random.choice(["SOUMIS", "EN_EVALUATION", "ATTRIBUE", "NON_RETENU"]),
                    round(random.uniform(500000, 40000000), 2),
                    ts(-8 + i), random.choice(["CONFORME", "NON_CONFORME", None]),
                    "Rapport de conformité automatique" if i % 2 == 0 else None,
                ),
            )
            soumission_ids.append(cur.fetchone()[0])

        # ============================================================
        # 7. EVALUATIONS SERVICE
        # ============================================================
        print("Seeding: comission_evaluation (evaluations_service)")
        eval_ce_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO comission_evaluation (id_service, nom_comission, categorie)
                   VALUES (%s,%s,%s) RETURNING id_comission""",
                (sc_ids[i % len(sc_ids)], f"Comité Éval ES {i+1}", random.choice(["Technique", "Financière", "Administrative"])),
            )
            eval_ce_ids.append(cur.fetchone()[0])

        print("Seeding: membres_commission_evaluation")
        for i in range(10):
            cur.execute(
                """INSERT INTO membres_commission_evaluation (id_comission, id_utilisateur)
                   VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                (eval_ce_ids[i % len(eval_ce_ids)], user_ids[i % len(user_ids)]),
            )

        print("Seeding: evaluation")
        for i in range(10):
            cur.execute(
                """INSERT INTO evaluation
                   (id_comission, id_soumission, id_utilisateur, type, note, commentaire, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    eval_ce_ids[i % len(eval_ce_ids)],
                    soumission_ids[i % len(soumission_ids)],
                    user_ids[i % len(user_ids)],
                    random.choice(["administrative", "technique", "financière"]),
                    random.randint(0, 100),
                    f"Évaluation #{i+1}: {'Satisfaisant' if random.random() > 0.3 else 'À améliorer'}",
                    ts(-3 + i), ts(),
                ),
            )

        # ============================================================
        # 8. CONTRATS SERVICE
        # ============================================================
        print("Seeding: validation")
        for i in range(10):
            cur.execute(
                """INSERT INTO validation
                   (id_utilisateur, id_soumission, type, is_validated, commentaire, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    user_ids[i % len(user_ids)],
                    soumission_ids[i % len(soumission_ids)],
                    random.choice(["interne", "externe", "tutelle"]),
                    random.choice([True, False]),
                    f"Commentaire de validation #{i+1}",
                    ts(-2 + i), ts(),
                ),
            )

        print("Seeding: contrats")
        contrat_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO contrats
                   (id_soumission, id_service_contractants, numero_contrat, date_signature, statut, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id_contrat""",
                (
                    soumission_ids[i % len(soumission_ids)],
                    sc_ids[i % len(sc_ids)],
                    f"CTR-2025-{3000+i}",
                    ts(-1 + i) if i % 3 != 0 else None,
                    random.choice(["brouillon", "signé", "en_cours", "terminé"]),
                    ts(-1 + i), ts(),
                ),
            )
            contrat_ids.append(cur.fetchone()[0])

        print("Seeding: documents_contrats")
        for i in range(10):
            cur.execute(
                """INSERT INTO documents_contrats (id_contrat, id_document)
                   VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                (contrat_ids[i % len(contrat_ids)], doc_ids[i % len(doc_ids)]),
            )

        # ============================================================
        # 9. NOTIFICATIONS
        # ============================================================
        print("Seeding: notifications")
        notif_types = ["APPEL_PUBLIE", "SOUMISSION_RECUE", "EVALUATION_TERMINEE", "CONTRAT_SIGNE", "RECOURS_DEPOSE"]
        categories  = ["appels", "soumissions", "evaluations", "contrats", "recours"]
        for i in range(10):
            cur.execute(
                """INSERT INTO notifications
                   (utilisateur_id, type_notification, titre, message, priorite, categorie,
                    entite_liee_type, entite_liee_id, statut, created_at, sent_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    user_ids[i % len(user_ids)],
                    notif_types[i % len(notif_types)],
                    f"Notification #{i+1}",
                    f"Vous avez une nouvelle notification concernant {categories[i % len(categories)]}.",
                    random.choice(["haute", "moyenne", "basse"]),
                    categories[i % len(categories)],
                    random.choice(["appel_offre", "soumission", "contrat"]),
                    appel_ids[i % len(appel_ids)],
                    random.choice(["envoyée", "lue", "archivée"]),
                    ts(-5 + i), ts(-4 + i),
                ),
            )

        # ============================================================
        # 10. IA SERVICE
        # ============================================================
        print("Seeding: detection_anomalie_ia")
        anomalie_types = [
            "MONTANT_TROP_ELEVE", "MONTANT_TROP_BAS", "PRIX_ANORMALEMENT_BAS",
            "PRIX_ANORMALEMENT_ELEVE", "SAUCISSONNAGE_TEMPOREL",
            "SOUMISSION_HORS_DELAI", "DISPERSION_ANORMALE",
            "ROTATION_SOUMISSIONNAIRES", "SAUCISSONNAGE_PROXIMITE_SEUIL",
            "MONTANT_FINANCIER_MANQUANT",
        ]
        for i in range(10):
            cur.execute(
                """INSERT INTO detection_anomalie_ia
                   (id_appel_offre, id_soumission, type_anomalie, niveau_severite,
                    score_confiance, details, soumissions_impliquees, appels_impliques,
                    statut_examen, commentaire_examen, date_detection)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    appel_ids[i % len(appel_ids)],
                    soumission_ids[i % len(soumission_ids)],
                    anomalie_types[i],
                    random.choice(["ERROR", "WARNING"]),
                    round(random.uniform(0.50, 0.99), 2),
                    f"Détails de l'anomalie #{i+1}: analyse automatique",
                    json.dumps([soumission_ids[i % len(soumission_ids)]]),
                    json.dumps([appel_ids[i % len(appel_ids)]]),
                    random.choice(["EN_ATTENTE", "EN_COURS", "VALIDE", "REJETE"]),
                    f"Commentaire examen #{i+1}" if i % 2 == 0 else "",
                    ts(-3 + i),
                ),
            )

        # ============================================================
        # 11. RECOURS
        # ============================================================
        print("Seeding: recours")
        recours_ids = []
        for i in range(10):
            cur.execute(
                """INSERT INTO recours
                   (id_operateur_economique, id_validation, id_soumission,
                    type_recours, objet, explications, motif, statut,
                    date_depot, date_limite, decision, traite_par, version,
                    created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id_recours""",
                (
                    i + 1, i + 1,
                    soumission_ids[i % len(soumission_ids)],
                    random.choice(["GRACIEUX", "HIERARCHIQUE", "CONTENTIEUX"]),
                    f"Objet du recours #{i+1}",
                    f"Explications détaillées pour le recours #{i+1}",
                    f"Motif de recours: irrégularité constatée #{i+1}",
                    random.choice(["DEPOSE", "EN_INSTRUCTION", "DECISION_PRISE", "ACCEPTE", "REJETE"]),
                    ts(-5 + i), ts(10 + i),
                    f"Décision #{i+1}" if i % 3 == 0 else None,
                    user_ids[i % len(user_ids)] if i % 2 == 0 else None,
                    0, ts(-5 + i), ts(),
                ),
            )
            recours_ids.append(cur.fetchone()[0])

        print("Seeding: documents_recours")
        for i in range(10):
            cur.execute(
                """INSERT INTO documents_recours (id_recours, id_document, created_at)
                   VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
                (recours_ids[i % len(recours_ids)], doc_ids[i % len(doc_ids)], ts(-4 + i)),
            )

        # ============================================================
        # 12. AUDIT / LEDGER
        # ============================================================
        print("Seeding: journaux_audit")
        prev_hash = b'\x00' * 32
        for i in range(10):
            current_hash = hashlib.sha256(prev_hash + str(i).encode()).digest()
            cur.execute(
                """INSERT INTO journaux_audit
                   (utilisateur_id, action, entite_type, entite_id,
                    horodatage, adresse_ip, details_action, hash_precedent, hash_actuel)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    user_ids[i % len(user_ids)],
                    random.choice(["CREATE", "UPDATE", "DELETE", "LOGIN", "APPROVE"]),
                    random.choice(["appel_offre", "soumission", "contrat", "utilisateur"]),
                    i + 1, ts(-10 + i),
                    f"192.168.1.{random.randint(10,254)}",
                    json.dumps({"detail": f"Action audit #{i+1}", "seed": True}),
                    prev_hash, current_hash,
                ),
            )
            prev_hash = current_hash

        print("Seeding: journaux_outbox")
        for i in range(10):
            cur.execute(
                """INSERT INTO journaux_outbox
                   (id, aggregate_type, aggregate_id, event_type, payload, status, trace_id, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (
                    rand_uuid(), "AuditLog", str(i + 1), "audit_log.created",
                    json.dumps({"log_id": i + 1, "action": "CREATE", "seed": True}),
                    random.choice(["PENDING", "PROCESSED"]),
                    rand_uuid(), ts(-9 + i),
                ),
            )

        # ============================================================
        # 13. READSTORE
        # ============================================================
        print("Seeding: audit_read_projection")
        for i in range(10):
            cur.execute(
                """INSERT INTO audit_read_projection
                   (id, utilisateur_id, action, entite_type, entite_id,
                    horodatage, adresse_ip, details_action)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (
                    i + 100000,
                    user_ids[i % len(user_ids)],
                    random.choice(["CREATE", "UPDATE", "DELETE", "LOGIN"]),
                    random.choice(["appel_offre", "soumission", "contrat"]),
                    i + 1, ts(-10 + i),
                    f"10.0.0.{random.randint(1,254)}",
                    json.dumps({"projection": True, "row": i + 1}),
                ),
            )

        # ============================================================
        conn.commit()
        print("\nAll tables seeded successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
