#!/usr/bin/env python3
"""
Demo seed for the Service Contractant (Al-Mizan) — generates a single transactional
seed.sql to stdout. Wipes existing accounts + domain data and rebuilds a clean,
logical Algerian dataset:
  - one login per role (13 roles), smallest emails, identical password
  - one Service Contractant (DTP Alger) owning every AO
  - existing Operateurs Economiques (Algerian companies)
  - 23 appels d'offres spread across the lifecycle
  - soumissions ONLY on AOs whose "ouverture des plis" date has passed
  - recours ONLY on AOs at the post-opening (contribution / contestation) stage
RBAC config (role / permission / Permission_role) is preserved.
"""
import base64, hashlib, secrets

PASSWORD = "Mizan@2026"

def django_pbkdf2(password, iterations=870000):
    salt = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                    for _ in range(22))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, salt, base64.b64encode(dk).decode().strip())

PWHASH = django_pbkdf2(PASSWORD)

def q(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"

out = []
def w(line=""): out.append(line)

# ---------------------------------------------------------------- fixed UUIDs
SC_ORG = "5c000000-0000-0000-0000-000000000001"
CM_ORG = "c0000000-0000-0000-0000-000000000001"
def oe_org(n): return "0e000000-0000-0000-0000-%012x" % n          # last8hex -> int n
def membre_uuid(n): return "00000000-0000-0000-0000-%012x" % n     # last segment hex -> int n

ID_SERVICE = 1            # Services_Contractants.id_service (integer) used by every AO
COM_ID = 1               # commission id (both capital + lowercase commission tables)

# ----------------------------------------------------------------- OE catalogue
# int id (= UUID last 8 hex) -> (nom, wilaya, secteur, nif, rc, email, tel)
OES = {
 1: ("SPA Cosider Travaux Publics", "Alger", "BTP / Travaux publics", "098216000000011", "16B0900011", "contact@cosider-tp.dz", "021456789"),
 2: ("ENGOA - Grands Ouvrages d'Art", "Alger", "Ouvrages d'art", "098216000000022", "16B0900022", "contact@engoa.dz", "021556677"),
 3: ("SARL Hydro-Amenagement Sud", "Ouargla", "Hydraulique", "098230000000033", "30B0700033", "info@hydrosud.dz", "029711122"),
 4: ("EURL Batir Algerie", "Blida", "Batiment", "098209000000044", "09B0500044", "contact@batir-dz.dz", "025413344"),
 5: ("SPA Routes et Ouvrages du Sahel", "Bechar", "Routes", "098208000000055", "08B0600055", "contact@ros-sahel.dz", "049812233"),
 6: ("SARL Atlas Travaux Publics", "Tizi Ouzou", "Travaux publics", "098215000000066", "15B0400066", "contact@atlas-tp.dz", "026223344"),
 7: ("SPA Mediterranee Construction", "Oran", "Construction", "098231000000077", "31B0800077", "contact@med-construction.dz", "041334455"),
 8: ("ETRHB Travaux Hydrauliques", "Alger", "Hydraulique / Batiment", "098216000000088", "16B0900088", "contact@etrhb.dz", "021667788"),
}

# ----------------------------------------------------------- accounts (per role)
# (id_role, role, email, membre_int, prenom, nom, fonction, org)
USERS = [
 (1,  "RESP_SC",                  "respo@sc.dz",  1,  "Karim",       "Belkacem",  "Responsable du service contractant", SC_ORG),
 (2,  "REDACTEUR_CDC",            "redac@sc.dz",  2,  "Amine",       "Boudiaf",   "Redacteur des cahiers des charges",  SC_ORG),
 (3,  "EVALUATEUR",               "eval@sc.dz",   3,  "Yacine",      "Hamdani",   "Evaluateur COPEO",                   SC_ORG),
 (4,  "MEMBRE_COMITE_TECHNIQUE",  "ct@sc.dz",     4,  "Sofiane",     "Meziane",   "Membre du comite technique",         SC_ORG),
 (5,  "RESP_VALID_INTERN",        "rvi@sc.dz",    5,  "Nadia",       "Cherif",    "Responsable validation interne",     SC_ORG),
 (6,  "VALIDATEUR_INTERNE_MARCHE","vim@sc.dz",    6,  "Lamia",       "Saadi",     "Validateur interne marche",          SC_ORG),
 (7,  "VALIDATEUR_INTERNE_CDC",   "vic@sc.dz",    7,  "Riad",        "Benali",    "Validateur interne CDC",             SC_ORG),
 (8,  "RESP_OE",                  "respo@oe.dz",  8,  "Mourad",      "Khelifi",   "Gerant",                             oe_org(1)),
 (9,  "PREPARATEUR_OE",           "prep@oe.dz",   9,  "Salim",       "Aouad",     "Preparateur des offres",             oe_org(1)),
 (10, "RESP_CM",                  "respo@cm.dz",  10, "Fatima Zohra","Brahimi",   "Responsable commission des marches", CM_ORG),
 (11, "VALIDATEUR_EXTERNE_MARCHE","vem@cm.dz",    11, "Omar",        "Tibourtine","Validateur externe marche",          CM_ORG),
 (12, "VALIDATEUR_EXTERNE_CDC",   "vec@cm.dz",    12, "Hassiba",     "Lounis",    "Validateur externe CDC",             CM_ORG),
 (13, "ADMIN",                    "admin@mizan.dz",13,"Administrateur","Systeme", "Administrateur",                     SC_ORG),
]
SC_DASH_MEMBRES = [1, 2, 3, 4, 5, 6, 7]   # resolve to ID_SERVICE via capital commission

# ------------------------------------------------------------- AO definitions
# state -> statut, etat_execution, (pub,lim,ouv) day offsets from now (None = NULL)
STATE = {
 "BROUILLON":     ("brouillon",   "brouillon",     (None, None, None)),
 "EN_VALIDATION": ("non_valide",  "brouillon",     (None, None, None)),
 "REFUSE":        ("refuse",      "brouillon",     (None, None, None)),
 "VALIDE":        ("valide",      "publie",        (5,    20,   22)),
 "OUVERT":        ("valide",      "publie",        (-10,  10,   12)),
 "CLOTURE_DEPOT": ("valide",      "depot_cloture", (-20,  -2,   3)),
 "EN_OUVERTURE":  ("valide",      "plis_ouverts",  (-30,  -12,  -2)),
 "CLOTURE":       ("ferme",       "plis_ouverts",  (-90,  -70,  -65)),
 "ANNULE":        ("annule",      "annule",        (-15,  None, None)),
 "INFRUCTUEUX":   ("infructueux", "plis_ouverts",  (-40,  -20,  -10)),
}

# (ref, titre, type_procedure, type_prestation, wilaya, secteur, localisation, montant, state)
AOS = [
 ("AO-2026-001","Rehabilitation de la RN1 troncon Boughezoul-Djelfa","publique","travaux","Djelfa","Routes","RN1 PK120-PK168",1850000000,"EN_OUVERTURE"),
 ("AO-2026-002","Construction d'un echangeur autoroutier a Reghaia","publique","travaux","Alger","Ouvrages d'art","Reghaia Est",2400000000,"EN_OUVERTURE"),
 ("AO-2026-003","Amenagement urbain du centre-ville de Blida","publique","travaux","Blida","Amenagement urbain","Centre-ville",680000000,"EN_OUVERTURE"),
 ("AO-2026-004","Renforcement du reseau AEP de la ville d'Ouargla","publique","travaux","Ouargla","Hydraulique","Zones Sud",520000000,"EN_OUVERTURE"),
 ("AO-2026-005","Modernisation de l'eclairage public d'Oran","publique","travaux","Oran","Amenagement urbain","Wilaya d'Oran",210000000,"CLOTURE"),
 ("AO-2026-006","Construction d'un ouvrage d'art sur Oued El Harrach","publique","travaux","Alger","Ouvrages d'art","Oued El Harrach",1300000000,"CLOTURE"),
 ("AO-2026-007","Travaux de voirie et assainissement a Tizi Ouzou","publique","travaux","Tizi Ouzou","Travaux publics","Nouvelle ville",430000000,"OUVERT"),
 ("AO-2026-008","Refection de la chaussee RN5 entree de Bouira","publique","travaux","Bouira","Routes","RN5 entree Est",260000000,"OUVERT"),
 ("AO-2026-009","Construction d'un collecteur principal a Bechar","publique","travaux","Bechar","Hydraulique","Quartier Debdaba",340000000,"OUVERT"),
 ("AO-2026-010","Amenagement d'un rond-point a Setif","restreint","travaux","Setif","Travaux publics","Entree Nord",95000000,"CLOTURE_DEPOT"),
 ("AO-2026-011","Renovation du siege de la wilaya d'Alger","restreint","travaux","Alger","Batiment","Rue Hassiba Ben Bouali",150000000,"CLOTURE_DEPOT"),
 ("AO-2026-012","Etude geotechnique pour le futur pont de Constantine","restreint","etudes","Constantine","Etudes","Vallee du Rhumel",48000000,"VALIDE"),
 ("AO-2026-013","Construction d'un mur de soutenement a Jijel","restreint","travaux","Jijel","Ouvrages d'art","Corniche",72000000,"VALIDE"),
 ("AO-2026-014","Travaux d'urgence sur digue de protection a Annaba","gre_a_gre","travaux","Annaba","Hydraulique","Front de mer",65000000,"EN_VALIDATION"),
 ("AO-2026-015","Rehabilitation d'un troncon routier endommage a Medea","gre_a_gre","travaux","Medea","Routes","RN1 PK80",58000000,"EN_VALIDATION"),
 ("AO-2026-016","Refection d'un reseau d'assainissement a Tlemcen","publique","travaux","Tlemcen","Hydraulique","Centre-ville",180000000,"EN_VALIDATION"),
 ("AO-2026-017","Fourniture de mobilier de bureau pour la DTP","consultation","fournitures","Alger","Equipement","Siege DTP",4200000,"BROUILLON"),
 ("AO-2026-018","Acquisition de materiel informatique","consultation","fournitures","Alger","Equipement","Siege DTP",6800000,"BROUILLON"),
 ("AO-2026-019","Entretien des espaces verts du siege","consultation","services","Alger","Services","Siege DTP",2900000,"BROUILLON"),
 ("AO-2026-020","Construction d'un dalot sur chemin de wilaya CW42","publique","travaux","Boumerdes","Ouvrages d'art","CW42",120000000,"REFUSE"),
 ("AO-2026-021","Amenagement d'une aire de stationnement a Mostaganem","publique","travaux","Mostaganem","Travaux publics","Port",88000000,"REFUSE"),
 ("AO-2026-022","Travaux de signalisation routiere a Skikda","publique","travaux","Skikda","Routes","Voie d'evitement",75000000,"INFRUCTUEUX"),
 ("AO-2026-023","Rehabilitation d'un ancien hangar technique a Batna","restreint","travaux","Batna","Batiment","Zone industrielle",110000000,"ANNULE"),
]

# ============================================================ SQL GENERATION
w("BEGIN;")
w("SET CONSTRAINTS ALL DEFERRED;")
w()
w("-- 1) Wipe accounts + domain data (RBAC config kept)")
WIPE = [
 "django_admin_log","notifications","soumission_evaluateur","attribution","soumissions",
 "documents_recours","recours","registre_reception","registre_integrite_confirmation",
 "assignation_ct","membres_commission_evaluation","comission_evaluation",
 "appels_offres_suivis","appels_offres_operateurs_invites","documents_appel","achats_simples",
 "appels_offres","documents",
 "\"Membres_Commission_evaluation\"","\"Membres_Commission_interne\"","\"Membres_Commission_Externe\"",
 "\"Comission_evaluation\"","\"Comission_interne\"","contractant_service_commissionexterne",
 "\"Services_Contractants\"",
 "acteurs_service_demandedocument","acteurs_service_demandeoperateur",
 "acteurs_service_commissionexterne","acteurs_service_operateureconomique",
 "acteurs_service_servicecontractant","utilisateurs","membre","organisation",
]
w("TRUNCATE %s RESTART IDENTITY CASCADE;" % ", ".join(WIPE))
w()

w("-- 2) Organisations")
w("INSERT INTO organisation (id_organisation, nom_officiel, adresse_siege, email_contact, type_entite, wilaya, secteur, created_at) VALUES")
rows = []
rows.append("(%s, %s, %s, %s, 'SERVICE_CONTRACTANT', 'Alger', 'Travaux publics', NOW())" % (
    q(SC_ORG), q("Direction des Travaux Publics de la Wilaya d'Alger"),
    q("Rue Hassiba Ben Bouali, Alger"), q("contact@dtp-alger.dz")))
rows.append("(%s, %s, %s, %s, 'COMMISSION_EXTERNE', 'Alger', 'Controle des marches publics', NOW())" % (
    q(CM_ORG), q("Commission de Controle des Marches Publics - Wilaya d'Alger"),
    q("Boulevard Mohamed V, Alger"), q("contact@cmp-alger.dz")))
for n,(nom,wil,sec,nif,rc,email,tel) in OES.items():
    rows.append("(%s, %s, %s, %s, 'OPERATEUR_ECONOMIQUE', %s, %s, NOW())" % (
        q(oe_org(n)), q(nom), q("Zone d'activite, "+wil), q(email), q(wil), q(sec)))
w(",\n".join(rows) + ";")
w()

w("-- 3) Typed entity rows")
w("INSERT INTO acteurs_service_servicecontractant (organisation_id, code_service, secteur_activite) VALUES (%s, 'DTP-16', 'Travaux publics');" % q(SC_ORG))
w("INSERT INTO acteurs_service_commissionexterne (organisation_id, numero_agrement, specialite, niveau_competence, seuil) VALUES (%s, 'AGR-16-2026', 'Marches de travaux', 'WILAYA', 200000000.00);" % q(CM_ORG))
oe_rows = ["(%s, %s, %s)" % (q(oe_org(n)), q(v[3]), q(v[4])) for n,v in OES.items()]
w("INSERT INTO acteurs_service_operateureconomique (organisation_id, nif, num_registre_commerce) VALUES\n" + ",\n".join(oe_rows) + ";")
w()

w("-- 4) Integer service + commissions (capital tables drive my-service resolution)")
w("INSERT INTO \"Services_Contractants\" (id_service, id_tutelle, categorie, code_ordonnateur) VALUES (%d, 16, 'Direction de wilaya', 'DTP-ALGER-16');" % ID_SERVICE)
w("INSERT INTO \"Comission_evaluation\" (id_comission, nom_comission, categorie, id_service) VALUES (%d, 'COPEO - DTP Alger', 'Travaux', %d);" % (COM_ID, ID_SERVICE))
w("INSERT INTO \"Comission_interne\" (id_comission_interne, nom_comission, type_comission, id_service) VALUES (1, 'Commission interne de validation - DTP Alger', 'parmanante', %d);" % ID_SERVICE)
cap = ["(%d, %d)" % (m, COM_ID) for m in SC_DASH_MEMBRES]
w("INSERT INTO \"Membres_Commission_evaluation\" (id_membre, id_comission) VALUES\n" + ",\n".join(cap) + ";")
w()

w("-- 5) Accounts (one per role) + membres")
mrows = []
for (rid, role, email, mint, prenom, nom, fonction, org) in USERS:
    mrows.append("(%s, %s, %s, %s, %s, NOW(), NOW())" % (
        q(membre_uuid(mint)), q(org), q(nom), q(prenom), q(fonction)))
w("INSERT INTO membre (id_membre, organisation_id, nom, prenom, fonction, created_at, updated_at) VALUES\n" + ",\n".join(mrows) + ";")
urows = []
for (rid, role, email, mint, prenom, nom, fonction, org) in USERS:
    urows.append("(%d, %s, %s, %s, %d, NOW(), NOW(), true, false)" % (
        rid, q(membre_uuid(mint)), q(email), q(PWHASH), rid))
w("INSERT INTO utilisateurs (id_utilisateur, id_membre, email, password_hash, id_role, created_at, updated_at, is_active, must_change_password) VALUES\n" + ",\n".join(urows) + ";")
w()

w("-- 6) COPEO membership (evaluations service) + CT assignment")
# id_utilisateur of eval(3), ct(4), rvi(5)
w("INSERT INTO comission_evaluation (id_comission, id_service, nom_comission, categorie) VALUES (%d, %d, 'COPEO - DTP Alger', 'Travaux');" % (COM_ID, ID_SERVICE))
w("INSERT INTO membres_commission_evaluation (id_utilisateur, id_comission, role_label) VALUES (3, %d, 'PRESIDENT'), (4, %d, 'MEMBRE'), (5, %d, 'MEMBRE');" % (COM_ID, COM_ID, COM_ID))
w("INSERT INTO assignation_ct (id_utilisateur, assigned_at, id_comission_id) VALUES (4, NOW(), %d);" % COM_ID)
w()

w("-- 7) OE inscription requests (pending in the SC inbox)")
import uuid as _uuid
DEMANDES = [
 ("SARL Constructions Modernes de Tipaza","contact@cmt-tipaza.dz","024501122","098242000000101","42B0300101"),
 ("EURL Genie Civil El-Bahdja","contact@elbahdja-gc.dz","021778899","098216000000102","16B0900102"),
 ("SPA Travaux Maritimes d'Annaba","contact@tma-annaba.dz","038556644","098223000000103","23B0200103"),
]
drows = []
for nom,email,tel,nif,rc in DEMANDES:
    drows.append("(%s, %s, %s, %s, %s, %s, 'EN_ATTENTE', NOW(), NOW(), '', %d)" % (
        q(str(_uuid.uuid4())), q(nom), q(email), q(tel), q(nif), q(rc), ID_SERVICE))
w("INSERT INTO acteurs_service_demandeoperateur (id, nom_organisation, email_contact, telephone, nif, num_registre_commerce, statut, cree_le, mis_a_jour_le, motif_rejet, id_service_contractant) VALUES\n" + ",\n".join(drows) + ";")
w()

w("-- 8) Documents (one CDC per AO) ")
doc_rows = []
for i,(ref,titre,*_rest) in enumerate(AOS, start=1):
    h = hashlib.sha256(ref.encode()).hexdigest()
    doc_rows.append("(%d, 'appel_offre', %s, 'CDC', %s, %s, false, 'verifie', NOW(), 245000)" % (
        i, q("CDC - %s.pdf" % ref), q("minio://almizan/cdc/%s.pdf" % ref), q(h)))
w("INSERT INTO documents (id_document, related_type, nom, type_document, storage_url, hash_sha256, is_encrypted, ia_verif_statut, uploaded_at, taille_fichier) VALUES\n" + ",\n".join(doc_rows) + ";")
w()

w("-- 9) Appels d'offres")
ao_rows = []
for i,(ref,titre,tp,tpr,wil,sec,loc,montant,state) in enumerate(AOS, start=1):
    statut, etat, (pub,lim,ouv) = STATE[state]
    def dt(off): return "NULL" if off is None else "NOW() + INTERVAL '%d days'" % off
    needs_com = tp in ("publique","restreint") and state not in ("BROUILLON","EN_VALIDATION","REFUSE")
    com = "'%d'" % COM_ID if needs_com else "NULL"
    pt, pf = (60, 40) if tpr in ("travaux","etudes") else (40, 60)
    desc = "Le present appel d'offres porte sur : %s. Marche relevant du secteur %s, wilaya de %s." % (titre, sec, wil)
    min_rev = min(int(float(montant) * 0.3), 2000000000)
    exp = 5 if tpr in ("travaux", "etudes") else 0
    qual = "Categorie travaux publics" if tpr in ("travaux","etudes") else ""
    ao_rows.append(
      "(%d, %d, %s, %s, %s, %s, %s, %s, %s, 'public', %s, %s, %s, %s, %s, %s, %s, %d, %d, 70, 'weighted', %d, 'interne', %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, %d, %s, %d, NOW(), NOW())" % (
        i, ID_SERVICE, com, q(ref), q(titre), q(tp), q(tpr), q(wil), q(sec), q(loc),
        str(montant), dt(pub), dt(lim), dt(ouv), q(statut), q(etat), pt, pf, i,
        q(desc), min_rev, q(qual), exp))
w("INSERT INTO appels_offres (id_appel_offres, id_service_contractant, commission_id, reference, titre, type_procedure, type_prestation, wilaya, secteur, visibilite, localisation, montant_estime, date_publication, date_limite_soumission, date_ouverture_plis, statut, etat_execution, poids_technique, poids_financier, seuil_technique, methodology, id_doc_cdc, validation_level, description, required_docs_admin, required_docs_tech, required_docs_fin, participation_conditions, minimum_revenue_da, qualification_category, minimum_experience_years, created_at, updated_at) VALUES\n" + ",\n".join(ao_rows) + ";")
w("INSERT INTO documents_appel (id_document, id_appel_offres) SELECT id_doc_cdc, id_appel_offres FROM appels_offres WHERE id_doc_cdc IS NOT NULL;")
w()

w("-- 10) Invited operateurs (restreint / gre_a_gre / consultation)")
inv_rows = []
oe_cycle = list(OES.keys())
for i,(ref,titre,tp,tpr,wil,sec,loc,montant,state) in enumerate(AOS, start=1):
    if tp == "publique":
        continue
    if tp == "gre_a_gre":
        invitees = [oe_cycle[i % len(oe_cycle)]]
    elif tp == "restreint":
        invitees = [oe_cycle[(i+k) % len(oe_cycle)] for k in range(4)]
    else:  # consultation
        invitees = [oe_cycle[(i+k) % len(oe_cycle)] for k in range(3)]
    for oe in sorted(set(invitees)):
        inv_rows.append("(%d, %d, 'invite', NOW(), NOW())" % (i, oe))
w("INSERT INTO appels_offres_operateurs_invites (id_appel_offres, id_operateur_economique, statut_invitation, created_at, updated_at) VALUES\n" + ",\n".join(inv_rows) + ";")
w()

w("-- 11) Soumissions — ONLY for AOs past 'ouverture des plis' (visible bids)")
# AO ids by state
opened_states = {"EN_OUVERTURE","CLOTURE","INFRUCTUEUX"}
soum_rows = []
soum_id = 0
soum_index = {}   # ao_id -> [(soum_id, oe_int, montant, statut)]
for i,(ref,titre,tp,tpr,wil,sec,loc,montant,state) in enumerate(AOS, start=1):
    if state not in opened_states:
        continue
    if state == "INFRUCTUEUX":
        bidders = [oe_cycle[(i) % len(oe_cycle)]]
        statuses = ["NON_RETENU"]
    elif state == "CLOTURE":
        bidders = [oe_cycle[(i+k) % len(oe_cycle)] for k in range(3)]
        statuses = ["ATTRIBUE","NON_RETENU","NON_RETENU"]
    else:  # EN_OUVERTURE
        bidders = [oe_cycle[(i+k) % len(oe_cycle)] for k in range(4)]
        statuses = ["EN_OUVERTURE","EN_OUVERTURE","EN_OUVERTURE","EN_OUVERTURE"]
    seen = set(); pairs = []
    for oe, st in zip(bidders, statuses):
        if oe in seen: continue
        seen.add(oe); pairs.append((oe, st))
    base = float(montant) * 0.9
    soum_index[i] = []
    for k,(oe, st) in enumerate(pairs):
        soum_id += 1
        m = round(base * (0.95 + 0.03*k), 2)
        url = "minio://almizan/soumissions/%s-oe%d.pdf.enc" % (ref, oe)
        soum_rows.append("(%d, %d, %d, %s, %s, '[]', %s, %s, NOW() - INTERVAL '%d days', 'conforme')" % (
            soum_id, i, oe, q(url), q("enc:"+hashlib.sha256((url).encode()).hexdigest()[:32]),
            q(st), str(m), 14))
        soum_index[i].append((soum_id, oe, m, st))
w("INSERT INTO soumissions (id_soumission, id_appel_offre, id_soumissionnaire, offre_financiere_chiffree_url, cle_dechiffrement_hash, document_ids, statut, montant_financier, date_soumission, conformite_statut) VALUES\n" + ",\n".join(soum_rows) + ";")
w()

w("-- 12) Registre de reception (COPEO) for the first opened AO")
reg_rows = []
first_open = next((i for i,(*_x,state) in enumerate(AOS, start=1) if AOS[i-1][8]=="EN_OUVERTURE"), None)
if first_open and soum_index.get(first_open):
    for ordre,(sid, oe, m, st) in enumerate(soum_index[first_open], start=1):
        reg_rows.append("(%d, %d, %s, NOW() - INTERVAL '2 days', NOW() - INTERVAL '14 days', false, %d)" % (
            sid, ordre, q(OES[oe][0]), COM_ID))
    w("INSERT INTO registre_reception (id_soumission, numero_ordre, nom_oe, received_at, submitted_at, hors_delai, id_comission_id) VALUES\n" + ",\n".join(reg_rows) + ";")
w()

w("-- 13) Recours — ONLY on AOs at the contribution / contestation stage (EN_OUVERTURE)")
rec_rows = []
rec_id = 0
en_ouv_aos = [i for i,(*_x,) in enumerate(AOS, start=1) if AOS[i-1][8]=="EN_OUVERTURE"]
# contest on the last (highest / non-retained) bid of the first 3 opened AOs
MOTIFS = [
 ("Contestation de l'evaluation technique","L'operateur conteste la notation technique de son offre.",
  "Le soumissionnaire estime que les criteres techniques n'ont pas ete appliques de maniere equitable."),
 ("Demande de reexamen de la conformite administrative","Piece administrative declaree manquante a tort.",
  "L'attestation CNAS fournie etait valide a la date de soumission."),
 ("Contestation du classement provisoire","Ecart de prix juge non justifie.",
  "L'operateur demande la verification du sous-detail des prix du classement provisoire."),
]
for k, ao_id in enumerate(en_ouv_aos[:3]):
    pairs = soum_index.get(ao_id, [])
    if not pairs: continue
    sid, oe, m, st = pairs[-1]
    rec_id += 1
    obj, expl, motif = MOTIFS[k % len(MOTIFS)]
    statut = "EN_INSTRUCTION" if k == 0 else "DEPOSE"
    rec_rows.append("(%d, %d, %d, %s, %s, NOW() - INTERVAL '3 days', NOW() + INTERVAL '7 days', 0, NOW(), NOW(), 'GRACIEUX', %s, %s)" % (
        oe, sid, 0, q(motif), q(statut), q(obj), q(expl)))
if rec_rows:
    w("INSERT INTO recours (id_operateur_economique, id_soumission, id_validation, motif, statut, date_depot, date_limite, version, created_at, updated_at, type_recours, objet, explications) VALUES\n" + ",\n".join(rec_rows) + ";")
w()

w("-- 14) Re-sync identity sequences after explicit ids")
for tbl,col in [("organisation",None),("appels_offres","id_appel_offres"),("documents","id_document"),
                ("soumissions","id_soumission"),("recours","id_recours"),("utilisateurs","id_utilisateur"),
                ("\"Services_Contractants\"","id_service"),("\"Comission_evaluation\"","id_comission"),
                ("comission_evaluation","id_comission")]:
    if col:
        w("SELECT setval(pg_get_serial_sequence('%s','%s'), GREATEST((SELECT COALESCE(MAX(%s),1) FROM %s),1));" % (tbl,col,col,tbl))
w()
w("COMMIT;")

print("\n".join(out))
