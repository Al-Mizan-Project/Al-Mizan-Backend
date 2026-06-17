import base64
import datetime as _dt
import hashlib
import hmac
import os
import secrets
import sys
import uuid as _uuid
from urllib.parse import quote, urlparse

try:
    from django.db import connection, transaction
    from auth_service.models import Permission, PermissionRole, Role
except Exception:
    connection = None
    transaction = None
    Permission = None
    PermissionRole = None
    Role = None


PASSWORD = "Mizan@2026"
ADMIN_PASSWORD = "Admin123!"
BUCKET = os.environ.get("MINIO_BUCKET_NAME", "almizan-documents")


ROLES_PERMISSIONS = {
    "ADMIN": [
        "organisation:create", "organisation:update", "organisation:deactivate",
        "user:create", "user:update", "user:deactivate",
        "role:manage", "seuil_cm:configure", "referentiel:manage",
        "log:read", "plateforme:configure",
    ],
    "RESP_SC": [
        "marche:create", "marche:read", "marche:update", "marche:publish",
        "marche:attribuer", "membre:create", "membre:update", "membre:deactivate",
        "oe:approuve", "oe:refuser", "role:assign",
        "offre:read_after_ouverture", "rapport:read", "recours:read",
    ],
    "REDACTEUR_CDC": [
        "marche:create", "marche:read", "marche:update",
        "cdc:create", "cdc:update", "cdc:submit_validation",
        "question:read", "question:repondre", "document:upload",
    ],
    "EVALUATEUR": [
        "registre_reception:read", "registre_reception:verify",
        "offre:flag_late", "offre:flag_identifying_marks", "offre:ecarted_before_opening",
        "seance_ouverture:read", "seance_ouverture:start", "seance_ouverture:close",
        "pli:open", "pli:read_content_after_opening", "offre:read_after_ouverture",
        "candidats_list:create", "candidats_list:read",
        "document_offre:paraph", "document_offre:read_after_paraph",
        "complement_request:propose", "complement_request:read",
        "complement_response:read", "document_complement:read",
        "conformite_formelle:evaluer", "offre:flag_anonymat_violation",
        "offre:flag_prix_divulgue_dans_pli_technique", "offre:ecarted_non_conformite",
        "interdiction_list:check", "conflict_interest:check", "exclusion:propose",
        "capacite_financiere:evaluer", "capacite_technique:evaluer",
        "capacite_professionnelle:evaluer", "capacite:noter",
        "offre:ecarted_capacite_insuffisante",
        "offre_technique:read", "offre_technique:evaluer", "offre_technique:noter",
        "critere_evaluation:read", "grille_notation:fill",
        "offre_technique:ecarted_note_insuffisante",
        "offre_financiere:block_if_technique_rejected",
        "offre_financiere:read", "offre_financiere:evaluer",
        "offre_financiere:controle_arithmetique",
        "offre_financiere:corriger_erreur_arithmetique",
        "offre_financiere:appliquer_marge_preference_nationale",
        "offre_financiere:noter",
        "prix_anormalement_bas:flag", "prix_anormalement_bas:analyze_justification",
        "prix_anormalement_bas:accept_justification", "prix_anormalement_bas:reject_justification",
        "prix_excessif:flag", "prix_excessif:propose_rejet",
        "atteinte_concurrence:flag", "atteinte_concurrence:propose_rejet",
        "classement:read", "classement:validate", "offre:propose_attribution",
        "document_original:read", "document_original:verify",
        "document_original:flag_non_conformite",
        "classement:reprendre_apres_exclusion", "offre:propose_infructuosite",
        "pv_ouverture:read", "pv_ouverture:signer", "pv_ouverture:add_reserve",
        "pv_evaluation:read", "pv_evaluation:create", "pv_evaluation:signer",
        "pv_evaluation:add_reserve",
        "pv_complementaire:create", "pv_complementaire:signer",
        "registre_ouverture_plis:read", "registre_evaluation_offres:read",
        "rapport_copeo:submit_to_sc",
    ],
    "MEMBRE_COMITE_TECHNIQUE": [
        "cahier_des_charges:read", "offre_technique:read", "document_offre:read",
        "analyse_technique:create", "analyse_technique:edit", "analyse_technique:read",
        "note_technique:create", "note_technique:edit",
        "commentaire_technique:add",
        "rapport_technique:create", "rapport_technique:edit",
        "rapport_technique:submit_to_copeo", "rapport_technique:read",
    ],
    "RESP_VALID_INTERN": [
        "dossier:read", "membre_civ:manage", "dossier:assigner", "rapport_cm:read",
    ],
    "VALIDATEUR_INTERNE_MARCHE": [
        "marche:valider_intern", "marche:rejeter_intern", "marche:read",
    ],
    "VALIDATEUR_INTERNE_CDC": [
        "cdc:read", "cdc:valider_intern", "cdc:rejeter_intern",
    ],
    "RESP_OE": [
        "appel_offre:read", "cdc:download",
        "offre:create", "offre:submit", "offre:signer",
        "offre:withdraw_before_deadline",
        "recours:create", "question:create",
        "membre_oe:manage", "profil_entreprise:update", "resultat:read",
    ],
    "PREPARATEUR_OE": [
        "appel_offre:read", "cdc:download",
        "offre:create", "offre:update", "document:upload", "offre:read_own",
    ],
    "RESP_CM": [
        "dossier:read", "visa:accorder", "visa:refuser",
        "membre_cm:manage", "dossier:assigner", "rapport_cm:read",
    ],
    "VALIDATEUR_EXTERNE_MARCHE": [
        "dossier:read", "marche:valider_extern", "marche:rejeter_extern",
    ],
    "VALIDATEUR_EXTERNE_CDC": [
        "dossier:read", "cdc:valider_extern", "cdc:rejeter_extern",
    ],
}


SC_ORG = "5c000000-0000-0000-0000-000000000001"
CM_ORG = "c0000000-0000-0000-0000-000000000001"
ID_SERVICE = 1
EVAL_COMMISSION_ID = 1
VALIDATION_COMMISSION_ID = 1


def oe_org(n):
    return "0e000000-0000-0000-0000-%012x" % n


def membre_uuid(n):
    return "00000000-0000-0000-0000-%012x" % n


def django_pbkdf2(password, iterations=870000):
    salt = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(22))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, salt, base64.b64encode(dk).decode().strip())


def q(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


OES = {
    1: ("SPA Cosider Travaux Publics", "Alger", "Travaux publics", "098216000000011", "16B0900011", "contact@cosider-tp.dz", "021456789"),
    2: ("ENGOA", "Alger", "Ouvrages d'art", "098216000000022", "16B0900022", "contact@engoa.dz", "021556677"),
    3: ("SARL Hydro Sud", "Ouargla", "Hydraulique", "098230000000033", "30B0700033", "info@hydrosud.dz", "029711122"),
    4: ("EURL Batir Algerie", "Blida", "Batiment", "098209000000044", "09B0500044", "contact@batir-dz.dz", "025413344"),
    5: ("SPA Routes Sahel", "Bechar", "Routes", "098208000000055", "08B0600055", "contact@routes-sahel.dz", "049812233"),
    6: ("SARL Atlas TP", "Tizi Ouzou", "Travaux publics", "098215000000066", "15B0400066", "contact@atlas-tp.dz", "026223344"),
    7: ("SPA Mediterranee Construction", "Oran", "Construction", "098231000000077", "31B0800077", "contact@med-construction.dz", "041334455"),
    8: ("EURL ETRHB Hydraulique", "Alger", "Hydraulique", "098216000000088", "16B0900088", "contact@etrhb.dz", "021667788"),
    9: ("SARL Electro Power", "Setif", "Electricite", "098219000000099", "19B1000099", "contact@electropower.dz", "036551234"),
    10: ("EURL Etudes Genie Civil", "Constantine", "Etudes", "098225000000110", "25B1100110", "contact@egc.dz", "031778822"),
    11: ("SPA Verts Paysage", "Blida", "Espaces verts", "098209000000121", "09B0500121", "contact@verts.dz", "025887766"),
    12: ("SARL InfoTech Solutions", "Alger", "Informatique", "098216000000132", "16B0900132", "contact@infotech-dz.dz", "021998877"),
    13: ("SARL Mobilier Pro", "Oran", "Fournitures", "098231000000143", "31B0800143", "contact@mobilierpro.dz", "041224466"),
    14: ("SPA Signalisation Routiere", "Annaba", "Signalisation", "098223000000154", "23B0200154", "contact@signalisation.dz", "038447755"),
}


# id_utilisateur, role, email, membre_int, prenom, nom, fonction, org_uuid
USERS = [
    (1, "RESP_SC", "respo@sc.dz", 1, "Karim", "Belkacem", "Responsable SC", SC_ORG),
    (2, "REDACTEUR_CDC", "redac@sc.dz", 2, "Amine", "Boudiaf", "Redacteur CDC", SC_ORG),
    (3, "EVALUATEUR", "eval@sc.dz", 3, "Yacine", "Hamdani", "Evaluateur", SC_ORG),
    (4, "MEMBRE_COMITE_TECHNIQUE", "ct@sc.dz", 4, "Sofiane", "Meziane", "Comite technique", SC_ORG),
    (5, "RESP_VALID_INTERN", "rvi@sc.dz", 5, "Nadia", "Cherif", "Resp. validation", SC_ORG),
    (6, "VALIDATEUR_INTERNE_MARCHE", "vim@sc.dz", 6, "Lamia", "Saadi", "Validateur marche", SC_ORG),
    (7, "VALIDATEUR_INTERNE_CDC", "vic@sc.dz", 7, "Riad", "Benali", "Validateur CDC", SC_ORG),
    (8, "RESP_OE", "respo@oe.dz", 8, "Mourad", "Khelifi", "Gerant", oe_org(1)),
    (9, "PREPARATEUR_OE", "prep@oe.dz", 9, "Salim", "Aouad", "Preparateur", oe_org(1)),
    (10, "RESP_CM", "respo@cm.dz", 10, "Fatima", "Brahimi", "Resp. commission", CM_ORG),
    (11, "VALIDATEUR_EXTERNE_MARCHE", "vem@cm.dz", 11, "Omar", "Tibourtine", "Validateur externe marche", CM_ORG),
    (12, "VALIDATEUR_EXTERNE_CDC", "vec@cm.dz", 12, "Hassiba", "Lounis", "Validateur externe CDC", CM_ORG),
    (13, "ADMIN", "admin@plateforme.dz", None, "Admin", "Systeme", "Administrateur", None),
    (101, "EVALUATEUR", "eval2@sc.dz", 101, "Hamza", "Belaid", "Evaluateur", SC_ORG),
    (102, "EVALUATEUR", "eval3@sc.dz", 102, "Karima", "Saidi", "Evaluatrice", SC_ORG),
    (103, "EVALUATEUR", "eval4@sc.dz", 103, "Bilal", "Ferhat", "Evaluateur", SC_ORG),
    (104, "MEMBRE_COMITE_TECHNIQUE", "ct2@sc.dz", 104, "Walid", "Mansouri", "Comite technique", SC_ORG),
    (105, "MEMBRE_COMITE_TECHNIQUE", "ct3@sc.dz", 105, "Samira", "Haddad", "Comite technique", SC_ORG),
    (106, "MEMBRE_COMITE_TECHNIQUE", "ct4@sc.dz", 106, "Tarek", "Belkhir", "Comite technique", SC_ORG),
]


SC_SERVICE_MEMBERS = [1, 2, 3, 4, 5, 6, 7, 101, 102, 103, 104, 105, 106]


STATE = {
    "EN_VALIDATION": ("non_valide", "brouillon", (None, None, None)),
    "REFUSE": ("refuse", "brouillon", (None, None, None)),
    "VALIDE": ("valide", "publie", (5, 20, 22)),
    "OUVERT": ("valide", "publie", (-10, 10, 12)),
    "CLOTURE_DEPOT": ("valide", "depot_cloture", (-20, -2, 3)),
    "EN_OUVERTURE": ("valide", "plis_ouverts", (-30, -12, -2)),
    "CLOTURE": ("ferme", "plis_ouverts", (-90, -70, -65)),
    "INFRUCTUEUX": ("ferme", "plis_ouverts", (-45, -25, -20)),
}
CONSULT_STATE = ("valide", "publie", (None, None, None))


# ref, title, procedure, prestation, wilaya, sector, place, amount, state
AOS = [
    ("AO-2026-001", "Rehabilitation RN1 Boughezoul-Djelfa", "publique", "travaux", "Djelfa", "Routes", "RN1 PK120", 1850000000, "EN_OUVERTURE"),
    ("AO-2026-002", "Echangeur autoroutier Reghaia", "publique", "travaux", "Alger", "Ouvrages d'art", "Reghaia", 2400000000, "EN_OUVERTURE"),
    ("AO-2026-003", "Reseau AEP Ouargla", "publique", "travaux", "Ouargla", "Hydraulique", "Ouargla", 520000000, "EN_OUVERTURE"),
    ("AO-2026-004", "Eclairage public Oran", "publique", "travaux", "Oran", "Electricite", "Oran", 210000000, "EN_OUVERTURE"),
    ("AO-2026-005", "Ouvrage d'art Oued El Harrach", "publique", "travaux", "Alger", "Ouvrages d'art", "El Harrach", 1300000000, "CLOTURE"),
    ("AO-2026-006", "Voirie Tizi Ouzou", "publique", "travaux", "Tizi Ouzou", "Travaux publics", "Nouvelle ville", 430000000, "CLOTURE"),
    ("AO-2026-007", "Chaussee RN5 Bouira", "publique", "travaux", "Bouira", "Routes", "RN5 Est", 260000000, "OUVERT"),
    ("AO-2026-008", "Collecteur principal Bechar", "publique", "travaux", "Bechar", "Hydraulique", "Debdaba", 340000000, "OUVERT"),
    ("AO-2026-009", "Centre-ville Blida", "publique", "travaux", "Blida", "Amenagement", "Blida centre", 680000000, "OUVERT"),
    ("AO-2026-010", "Rond-point Setif Nord", "restreint", "travaux", "Setif", "Travaux publics", "Setif Nord", 95000000, "CLOTURE_DEPOT"),
    ("AO-2026-011", "Siege wilaya Alger", "restreint", "travaux", "Alger", "Batiment", "Hassiba", 150000000, "CLOTURE_DEPOT"),
    ("AO-2026-012", "Etude pont Constantine", "restreint", "etudes", "Constantine", "Etudes", "Rhumel", 48000000, "VALIDE"),
    ("AO-2026-013", "Mur de soutenement Jijel", "restreint", "travaux", "Jijel", "Ouvrages d'art", "Corniche", 72000000, "VALIDE"),
    ("AO-2026-014", "Digue de protection Annaba", "gre_a_gre", "travaux", "Annaba", "Hydraulique", "Front de mer", 65000000, "EN_VALIDATION"),
    ("AO-2026-015", "Route endommagee Medea", "gre_a_gre", "travaux", "Medea", "Routes", "RN1 PK80", 58000000, "EN_VALIDATION"),
    ("AO-2026-016", "Assainissement Tlemcen", "publique", "travaux", "Tlemcen", "Hydraulique", "Tlemcen centre", 180000000, "EN_VALIDATION"),
    ("AO-2026-017", "Mobilier DTP", "consultation", "fournitures", "Alger", "Fournitures", "DTP Alger", 4200000, "VALIDE"),
    ("AO-2026-018", "Materiel informatique", "consultation", "fournitures", "Alger", "Informatique", "DTP Alger", 6800000, "VALIDE"),
    ("AO-2026-019", "Dalot CW42 Boumerdes", "publique", "travaux", "Boumerdes", "Ouvrages d'art", "CW42", 120000000, "REFUSE"),
    ("AO-2026-020", "Signalisation Skikda", "publique", "travaux", "Skikda", "Routes", "Skikda", 75000000, "INFRUCTUEUX"),
]

SUBMISSION_STATES = {"OUVERT", "CLOTURE_DEPOT", "EN_OUVERTURE", "CLOTURE", "INFRUCTUEUX"}
OPENED_STATES = {"EN_OUVERTURE", "CLOTURE", "INFRUCTUEUX"}
ANNEXE_STATES = {"VALIDE", "OUVERT", "CLOTURE_DEPOT", "EN_OUVERTURE", "CLOTURE", "INFRUCTUEUX"}


def make_pdf(title, lines):
    def esc(text):
        return str(text).replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    parts = [
        "BT", "/F1 16 Tf", "1 0 0 1 60 780 Tm", "(%s) Tj" % esc(title), "ET",
        "BT", "/F1 11 Tf", "1 0 0 1 60 745 Tm", "16 TL",
    ]
    for index, line in enumerate(lines):
        parts.append("(%s) Tj" % esc(line) if index == 0 else "T* (%s) Tj" % esc(line))
    parts.append("ET")
    content = "\n".join(parts).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % index + body + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_pos)
    return bytes(pdf)


DOCUMENTS = []
AO_DOCS = {}


def add_document(ao_id, ref, title, sector, wilaya, kind):
    labels = {
        "cdc": ("CDC", "Cahier des charges"),
        "justification": ("JUSTIFICATION", "Justification procedure"),
        "besoin": ("BESOIN", "Expression du besoin"),
        "annexe": ("ANNEXE", "Annexe technique"),
    }
    doc_id = len(DOCUMENTS) + 1
    code, label = labels[kind]
    name = "%s - %s.pdf" % (label, ref)
    key = "seed/%s/%s.pdf" % (kind, ref)
    lines = [
        "Reference : %s" % ref,
        "Objet : %s" % title,
        "Secteur : %s" % sector,
        "Wilaya : %s" % wilaya,
        "Service contractant : DTP Alger",
        "Document demo Al-Mizan : %s" % label,
    ]
    pdf = make_pdf(label, lines)
    DOCUMENTS.append({
        "id": doc_id,
        "key": key,
        "nom": name,
        "type_document": "application/pdf",
        "type_code": code,
        "title": label,
        "lines": lines,
        "storage_url": key,
        "hash": hashlib.sha256(pdf).hexdigest(),
        "size": len(pdf),
        "ao_id": ao_id,
        "kind": kind,
    })
    return doc_id


for ao_id, (ref, title, procedure, prestation, wilaya, sector, place, amount, state) in enumerate(AOS, start=1):
    docs = {"cdc": None, "justification": None, "besoin": None, "annexes": []}
    docs["cdc"] = add_document(ao_id, ref, title, sector, wilaya, "cdc")
    if procedure in ("restreint", "gre_a_gre"):
        docs["justification"] = add_document(ao_id, ref, title, sector, wilaya, "justification")
    if procedure == "consultation":
        docs["besoin"] = add_document(ao_id, ref, title, sector, wilaya, "besoin")
    if state in ANNEXE_STATES:
        docs["annexes"].append(add_document(ao_id, ref, title, sector, wilaya, "annexe"))
    AO_DOCS[ao_id] = docs


def build_demo_sql(password_hash, admin_hash, wrap=True):
    lines = []

    def w(line=""):
        lines.append(line)

    if wrap:
        w("BEGIN;")
        w("SET CONSTRAINTS ALL DEFERRED;")

    w("-- Wipe accounts + demo domain data; RBAC tables are preserved")
    wipe = [
        "public.django_admin_log", "public.notifications",
        "public.soumission_evaluateur", "public.attribution", "public.soumissions",
        "public.documents_recours", "public.recours",
        "public.paraphe_membre", "public.pli_ouverture", "public.seance_ouverture",
        "public.registre_reception", "public.registre_integrite_confirmation",
        "public.assignation_ct", "public.membres_commission_evaluation", "public.comission_evaluation",
        "public.appels_offres_suivis", "public.appels_offres_operateurs_invites",
        "public.documents_appel", "public.achats_simples", "public.appels_offres", "public.documents",
        'public."Membres_Commission_evaluation"', 'public."Membres_Commission_interne"',
        'public."Membres_Commission_Externe"', 'public."Comission_evaluation"',
        'public."Comission_interne"', "public.contractant_service_commissionexterne",
        'public."Services_Contractants"', "public.acteurs_service_demandedocument",
        "public.acteurs_service_demandeoperateur", "public.acteurs_service_commissionexterne",
        "public.acteurs_service_operateureconomique", "public.acteurs_service_servicecontractant",
        "public.utilisateurs", "public.membre", "public.organisation",
    ]
    w("DO $$")
    w("DECLARE t text;")
    w("BEGIN")
    w("  FOREACH t IN ARRAY ARRAY[%s] LOOP" % ", ".join(q(table) for table in wipe))
    w("    IF to_regclass(t) IS NOT NULL THEN")
    w("      EXECUTE 'TRUNCATE TABLE ' || t || ' RESTART IDENTITY CASCADE';")
    w("    END IF;")
    w("  END LOOP;")
    w("END $$;")
    w()

    w("-- Organisations")
    org_rows = [
        "(%s, %s, %s, %s, 'SERVICE_CONTRACTANT', 'Alger', 'Travaux publics', NOW())" % (
            q(SC_ORG), q("Direction des Travaux Publics d'Alger"), q("Alger Centre"), q("contact@dtp-alger.dz")
        ),
        "(%s, %s, %s, %s, 'COMMISSION_EXTERNE', 'Alger', 'Marches publics', NOW())" % (
            q(CM_ORG), q("Commission des Marches Publics Alger"), q("Alger"), q("contact@cmp-alger.dz")
        ),
    ]
    for n, (name, wilaya, sector, nif, rc, email, phone) in OES.items():
        org_rows.append("(%s, %s, %s, %s, 'OPERATEUR_ECONOMIQUE', %s, %s, NOW())" % (
            q(oe_org(n)), q(name), q("ZA " + wilaya), q(email), q(wilaya), q(sector)
        ))
    w("INSERT INTO organisation (id_organisation, nom_officiel, adresse_siege, email_contact, type_entite, wilaya, secteur, created_at) VALUES")
    w(",\n".join(org_rows) + ";")
    w()

    w("-- Typed organisations")
    w("INSERT INTO acteurs_service_servicecontractant (organisation_id, code_service, secteur_activite) VALUES (%s, 'DTP-16', 'Travaux publics');" % q(SC_ORG))
    w("INSERT INTO acteurs_service_commissionexterne (organisation_id, numero_agrement, specialite, niveau_competence, seuil) VALUES (%s, 'AGR-16-2026', 'Marches de travaux', 'WILAYA', 200000000.00);" % q(CM_ORG))
    oe_rows = ["(%s, %s, %s)" % (q(oe_org(n)), q(data[3]), q(data[4])) for n, data in OES.items()]
    w("INSERT INTO acteurs_service_operateureconomique (organisation_id, nif, num_registre_commerce) VALUES\n" + ",\n".join(oe_rows) + ";")
    w()

    w("-- Service and initial commissions")
    w('INSERT INTO "Services_Contractants" (id_service, id_tutelle, categorie, code_ordonnateur) VALUES (%d, 16, \'Direction de wilaya\', \'DTP-ALGER-16\');' % ID_SERVICE)
    w('INSERT INTO "Comission_evaluation" (id_comission, nom_comission, categorie, id_service) VALUES (%d, \'Commission evaluation DTP Alger\', \'Travaux\', %d);' % (EVAL_COMMISSION_ID, ID_SERVICE))
    w('INSERT INTO "Comission_interne" (id_comission_interne, nom_comission, type_comission, id_service) VALUES (%d, \'Commission validation DTP Alger\', \'parmanante\', %d);' % (VALIDATION_COMMISSION_ID, ID_SERVICE))
    w('INSERT INTO "Membres_Commission_evaluation" (id_membre, id_comission) VALUES\n' + ",\n".join("(%d, %d)" % (user_id, EVAL_COMMISSION_ID) for user_id in SC_SERVICE_MEMBERS) + ";")
    w('INSERT INTO "Membres_Commission_interne" (id_membre, id_commision_interne) VALUES (5, 1), (6, 1), (7, 1);')
    w()

    w("-- Membres and users")
    member_rows = []
    user_rows = []
    for user_id, role, email, member_int, first_name, last_name, function, org in USERS:
        member_id = "00000000-0000-0000-0000-000000000000" if member_int is None else membre_uuid(member_int)
        user_password = admin_hash if role == "ADMIN" else password_hash
        if member_int is not None:
            member_rows.append("(%s, %s, %s, %s, %s, NOW(), NOW())" % (
                q(member_id), q(org), q(last_name), q(first_name), q(function)
            ))
        user_rows.append("(%d, %s, %s, %s, (SELECT id_role FROM role WHERE nom_role = %s), NOW(), NOW(), true, false)" % (
            user_id, q(member_id), q(email), q(user_password), q(role)
        ))
    w("INSERT INTO membre (id_membre, organisation_id, nom, prenom, fonction, created_at, updated_at) VALUES\n" + ",\n".join(member_rows) + ";")
    w("INSERT INTO utilisateurs (id_utilisateur, id_membre, email, password_hash, id_role, created_at, updated_at, is_active, must_change_password) VALUES\n" + ",\n".join(user_rows) + ";")
    w()

    w("-- Evaluation-service commission + technical committee")
    w("INSERT INTO comission_evaluation (id_comission, id_service, nom_comission, categorie) VALUES (%d, %d, 'Commission evaluation DTP Alger', 'Travaux publics');" % (EVAL_COMMISSION_ID, ID_SERVICE))
    w("INSERT INTO membres_commission_evaluation (id_utilisateur, id_comission, role_label) VALUES (3, 1, 'president'), (101, 1, 'secretaire'), (102, 1, 'membre');")
    w("INSERT INTO assignation_ct (id_utilisateur, assigned_at, id_comission_id) VALUES (4, NOW(), 1), (104, NOW(), 1);")
    w()

    demandes = [
        ("SARL Constructions Tipaza", "contact@cmt-tipaza.dz", "024501122", "098242000000201", "42B0300201"),
        ("EURL Genie Civil El Bahdja", "contact@elbahdja-gc.dz", "021778899", "098216000000202", "16B0900202"),
        ("SPA Travaux Maritimes Annaba", "contact@tma-annaba.dz", "038556644", "098223000000203", "23B0200203"),
        ("SARL Forage Sud", "contact@forage-sud.dz", "029661177", "098230000000204", "30B0700204"),
        ("EURL Voiries Constantine", "contact@voiries-const.dz", "031442200", "098225000000205", "25B1100205"),
        ("SARL Equipements Setif", "contact@equip-setif.dz", "036220099", "098219000000206", "19B1000206"),
        ("SPA Batiments Ouest", "contact@bat-ouest.dz", "041337788", "098231000000207", "31B0800207"),
        ("EURL Topographie Mitidja", "contact@topo-mitidja.dz", "025119933", "098209000000208", "09B0500208"),
    ]
    demande_rows = ["(%s, %s, %s, %s, %s, %s, 'EN_ATTENTE', NOW(), NOW(), '', %d)" % (
        q(str(_uuid.uuid4())), q(name), q(email), q(phone), q(nif), q(rc), ID_SERVICE
    ) for name, email, phone, nif, rc in demandes]
    w("INSERT INTO acteurs_service_demandeoperateur (id, nom_organisation, email_contact, telephone, nif, num_registre_commerce, statut, cree_le, mis_a_jour_le, motif_rejet, id_service_contractant) VALUES\n" + ",\n".join(demande_rows) + ";")
    w()

    w("-- Documents")
    doc_rows = ["(%d, 'appel_offre', %s, %s, %s, %s, false, 'VALID', NOW(), %d)" % (
        doc["id"], q(doc["nom"]), q(doc["type_document"]), q(doc["storage_url"]), q(doc["hash"]), doc["size"]
    ) for doc in DOCUMENTS]
    w("INSERT INTO documents (id_document, related_type, nom, type_document, storage_url, hash_sha256, is_encrypted, ia_verif_statut, uploaded_at, taille_fichier) VALUES\n" + ",\n".join(doc_rows) + ";")
    w()

    w("-- Appels d'offres")
    ao_rows = []
    oe_ids = list(OES.keys())
    for ao_id, (ref, title, procedure, prestation, wilaya, sector, place, amount, state) in enumerate(AOS, start=1):
        statut, execution, (pub, limit, opening) = CONSULT_STATE if procedure == "consultation" else STATE[state]

        def dt(offset):
            return "NULL" if offset is None else "NOW() + INTERVAL '%d days'" % offset

        docs = AO_DOCS[ao_id]
        commission = "'%d'" % EVAL_COMMISSION_ID if procedure in ("publique", "restreint") and state not in ("EN_VALIDATION", "REFUSE") else "NULL"
        chosen_oe = "NULL"
        if procedure in ("gre_a_gre", "consultation"):
            chosen_oe = str(oe_ids[ao_id % len(oe_ids)])
        tech, fin = (60, 40) if prestation in ("travaux", "etudes") else (40, 60)
        min_revenue = min(int(float(amount) * 0.30), 2000000000)
        experience = 5 if prestation in ("travaux", "etudes") else 0
        qualification = "Travaux publics" if prestation in ("travaux", "etudes") else ""
        description = "%s. Secteur %s, wilaya %s." % (title, sector, wilaya)
        justif = str(docs["justification"]) if docs["justification"] else "NULL"
        besoin = str(docs["besoin"]) if docs["besoin"] else "NULL"
        ao_rows.append(
            "(%d, %d, %s, %s, %s, %s, %s, %s, %s, %s, 'public', %s, %s, %s, %s, %s, %d, %d, 70, "
            "'weighted', %s, %s, %s, %s, 'interne', %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, "
            "'[]'::jsonb, %d, %s, %d, %s, NOW(), NOW())" % (
                ao_id, ID_SERVICE, commission, q(ref), q(title), q(description), q(procedure), q(prestation),
                q(wilaya), q(sector), q(place), str(amount), dt(pub), dt(limit), dt(opening),
                tech, fin, str(docs["cdc"]), justif, besoin, chosen_oe, q(statut), min_revenue,
                q(qualification), experience, q(execution)
            )
        )
    w("INSERT INTO appels_offres (id_appel_offres, id_service_contractant, commission_id, reference, titre, description, type_procedure, type_prestation, wilaya, secteur, visibilite, localisation, montant_estime, date_publication, date_limite_soumission, date_ouverture_plis, poids_technique, poids_financier, seuil_technique, methodology, id_doc_cdc, id_doc_justification, id_doc_besoin, id_operateur_choisi, validation_level, statut, required_docs_admin, required_docs_tech, required_docs_fin, participation_conditions, minimum_revenue_da, qualification_category, minimum_experience_years, etat_execution, created_at, updated_at) VALUES\n" + ",\n".join(ao_rows) + ";")
    w()

    link_rows = []
    for ao_id in range(1, len(AOS) + 1):
        docs = AO_DOCS[ao_id]
        for doc_id in [docs["cdc"]] + docs["annexes"]:
            link_rows.append("(%d, %d)" % (doc_id, ao_id))
    w("INSERT INTO documents_appel (id_document, id_appel_offres) VALUES\n" + ",\n".join(link_rows) + ";")
    w()

    invite_rows = []
    for ao_id, (ref, title, procedure, prestation, wilaya, sector, place, amount, state) in enumerate(AOS, start=1):
        if procedure != "restreint":
            continue
        invitees = sorted({oe_ids[(ao_id + offset) % len(oe_ids)] for offset in range(4)})
        for oe_id in invitees:
            invite_rows.append("(%d, %d, 'invite', NOW(), NOW())" % (ao_id, oe_id))
    if invite_rows:
        w("INSERT INTO appels_offres_operateurs_invites (id_appel_offres, id_operateur_economique, statut_invitation, created_at, updated_at) VALUES\n" + ",\n".join(invite_rows) + ";")
    w()

    w("-- Soumissions exist only once a market can logically receive bids")
    soumission_rows = []
    soumission_index = {}
    soumission_id = 0
    for ao_id, (ref, title, procedure, prestation, wilaya, sector, place, amount, state) in enumerate(AOS, start=1):
        if state not in SUBMISSION_STATES:
            continue
        bidder_count = 1 if state == "INFRUCTUEUX" else (6 if state in ("OUVERT", "CLOTURE_DEPOT") else 4)
        statuses = []
        for idx in range(bidder_count):
            if state in {"OUVERT", "CLOTURE_DEPOT"}:
                statuses.append("SOUMIS")
            elif state == "CLOTURE" and idx == 0:
                statuses.append("ATTRIBUE")
            elif state == "INFRUCTUEUX":
                statuses.append("INFRUCTUEUX")
            else:
                statuses.append("EN_OUVERTURE")
        bidders = [oe_ids[(ao_id + offset) % len(oe_ids)] for offset in range(bidder_count)]
        base = float(amount) * 0.90
        soumission_index[ao_id] = []
        for idx, (oe_id, status) in enumerate(zip(bidders, statuses)):
            soumission_id += 1
            montant = "NULL" if state in {"OUVERT", "CLOTURE_DEPOT"} else str(round(base * (0.96 + 0.025 * idx), 2))
            url = "minio://almizan/soumissions/%s-oe%d.pdf.enc" % (ref, oe_id)
            soumission_rows.append("(%d, %d, %d, %s, %s, '[]'::jsonb, %s, %s, NOW() - INTERVAL '8 days', %s)" % (
                soumission_id, ao_id, oe_id, q(url), q("enc:" + hashlib.sha256(url.encode()).hexdigest()[:32]),
                q(status), montant, q(None if state in {"OUVERT", "CLOTURE_DEPOT"} else "conforme")
            ))
            soumission_index[ao_id].append((soumission_id, oe_id, montant, status))
    if soumission_rows:
        w("INSERT INTO soumissions (id_soumission, id_appel_offre, id_soumissionnaire, offre_financiere_chiffree_url, cle_dechiffrement_hash, document_ids, statut, montant_financier, date_soumission, conformite_statut) VALUES\n" + ",\n".join(soumission_rows) + ";")
    w()

    first_open = next((ao_id for ao_id in range(1, len(AOS) + 1) if AOS[ao_id - 1][8] == "EN_OUVERTURE"), None)
    if first_open and soumission_index.get(first_open):
        registre_rows = []
        for order, (sid, oe_id, amount, status) in enumerate(soumission_index[first_open], start=1):
            registre_rows.append("(%d, %d, %s, NOW() - INTERVAL '2 days', NOW() - INTERVAL '8 days', false, %d)" % (
                sid, order, q(OES[oe_id][0]), EVAL_COMMISSION_ID
            ))
        w("INSERT INTO registre_reception (id_soumission, numero_ordre, nom_oe, received_at, submitted_at, hors_delai, id_comission_id) VALUES\n" + ",\n".join(registre_rows) + ";")
    w()

    recours_rows = []
    motifs = [
        ("Notation technique contestee", "L'operateur conteste la notation technique.", "Demande de reexamen technique."),
        ("Piece administrative contestee", "Une piece a ete declaree manquante a tort.", "Verification de conformite demandee."),
        ("Classement provisoire conteste", "Le classement est juge incoherent.", "Controle du sous-detail des prix."),
    ]
    open_aos = [ao_id for ao_id in range(1, len(AOS) + 1) if AOS[ao_id - 1][8] == "EN_OUVERTURE"]
    for index, ao_id in enumerate(open_aos[:3]):
        pairs = soumission_index.get(ao_id, [])
        if not pairs:
            continue
        sid, oe_id, amount, status = pairs[-1]
        obj, expl, motif = motifs[index % len(motifs)]
        recours_rows.append("(%d, %d, NULL, %s, %s, NOW() - INTERVAL '3 days', NOW() + INTERVAL '7 days', 0, NOW(), NOW(), 'GRACIEUX', %s, %s)" % (
            oe_id, sid, q(motif), q("EN_INSTRUCTION" if index == 0 else "DEPOSE"), q(obj), q(expl)
        ))
    if recours_rows:
        w("INSERT INTO recours (id_operateur_economique, id_soumission, id_validation, motif, statut, date_depot, date_limite, version, created_at, updated_at, type_recours, objet, explications) VALUES\n" + ",\n".join(recours_rows) + ";")
    w()

    for table, column in [
        ("appels_offres", "id_appel_offres"), ("documents", "id_document"),
        ("soumissions", "id_soumission"), ("recours", "id_recours"),
        ("utilisateurs", "id_utilisateur"), ('"Services_Contractants"', "id_service"),
        ('"Comission_evaluation"', "id_comission"), ('"Comission_interne"', "id_comission_interne"),
        ('"Membres_Commission_evaluation"', "id"), ('"Membres_Commission_interne"', "id"),
        ("comission_evaluation", "id_comission"), ("membres_commission_evaluation", "id"),
        ("assignation_ct", "id"), ("registre_reception", "id"),
    ]:
        w("SELECT setval(pg_get_serial_sequence('%s','%s'), GREATEST((SELECT COALESCE(MAX(%s),1) FROM %s),1));" % (table, column, column, table))

    if wrap:
        w("COMMIT;")
    return "\n".join(lines)


def ensure_roles_permissions():
    print("=== Creation des roles et permissions ===")
    for role_name, permissions in ROLES_PERMISSIONS.items():
        role, role_created = Role.objects.get_or_create(nom_role=role_name)
        print("  [%s] Role : %s" % ("+" if role_created else "=", role_name))
        for perm_name in permissions:
            perm, _ = Permission.objects.get_or_create(nom_permission=perm_name)
            PermissionRole.objects.get_or_create(id_role=role, id_permission=perm)


def _aws_signing_key(secret_key, date_stamp, region, service):
    key = ("AWS4" + secret_key).encode()
    key = hmac.new(key, date_stamp.encode(), hashlib.sha256).digest()
    key = hmac.new(key, region.encode(), hashlib.sha256).digest()
    key = hmac.new(key, service.encode(), hashlib.sha256).digest()
    return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def _signed_s3_request(method, bucket, key="", body=b"", content_type=None):
    import requests

    endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000").rstrip("/")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "admin_almizan")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "SecurePassword123!")
    region = "us-east-1"
    parsed = urlparse(endpoint)
    path = "/%s%s" % (bucket, ("/" + key) if key else "")
    url = endpoint + path
    now = _dt.datetime.now(_dt.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {
        "host": parsed.netloc,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if content_type:
        headers["content-type"] = content_type

    signed_header_keys = sorted(headers)
    canonical_headers = "".join("%s:%s\n" % (name, headers[name]) for name in signed_header_keys)
    signed_headers = ";".join(signed_header_keys)
    canonical_request = "\n".join([
        method,
        quote(path, safe="/~"),
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    scope = "%s/%s/s3/aws4_request" % (date_stamp, region)
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])
    signature = hmac.new(_aws_signing_key(secret_key, date_stamp, region, "s3"), string_to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
        access_key, scope, signed_headers, signature
    )
    return requests.request(method, url, data=body if method != "HEAD" else None, headers=headers, timeout=15)


def upload_seed_documents():
    try:
        import boto3
        from botocore.client import Config
        from botocore.exceptions import ClientError

        endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "admin_almizan"),
            aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "SecurePassword123!"),
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        try:
            s3.head_bucket(Bucket=BUCKET)
        except ClientError:
            s3.create_bucket(Bucket=BUCKET)
        for doc in DOCUMENTS:
            s3.put_object(Bucket=BUCKET, Key=doc["key"], Body=make_pdf(doc["title"], doc["lines"]), ContentType="application/pdf")
    except Exception:
        head = _signed_s3_request("HEAD", BUCKET)
        if head.status_code == 404:
            create = _signed_s3_request("PUT", BUCKET)
            create.raise_for_status()
        elif head.status_code not in (200, 301, 403):
            head.raise_for_status()
        for doc in DOCUMENTS:
            response = _signed_s3_request("PUT", BUCKET, doc["key"], make_pdf(doc["title"], doc["lines"]), "application/pdf")
            response.raise_for_status()
    print("Uploaded %d seeded PDF document(s) to MinIO bucket '%s'." % (len(DOCUMENTS), BUCKET))


def run_seed():
    if connection is None:
        raise RuntimeError("Run this file through Django shell, or use --sql / --upload-files from the host.")
    with transaction.atomic():
        ensure_roles_permissions()
        sql = build_demo_sql(django_pbkdf2(PASSWORD), django_pbkdf2(ADMIN_PASSWORD), wrap=False)
        with connection.cursor() as cursor:
            cursor.execute(sql)
    upload_seed_documents()
    print("\n=== INITIALISATION TERMINEE ===")
    print("  Demo users password: %s" % PASSWORD)
    print("  Admin password: %s" % ADMIN_PASSWORD)
    print("  AOs: %d" % len(AOS))
    print("  Documents: %d" % len(DOCUMENTS))
    print("  OE demandes: 8")


if __name__ == "__main__":
    if "--sql" in sys.argv:
        print(build_demo_sql(django_pbkdf2(PASSWORD), django_pbkdf2(ADMIN_PASSWORD), wrap=True))
    elif "--upload-files" in sys.argv:
        upload_seed_documents()
    else:
        run_seed()
