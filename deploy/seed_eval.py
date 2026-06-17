"""
Seed script for Al-Mizan evaluation flow testing.
Run: python manage.py shell < deploy/seed.py
"""

import uuid
from django.utils import timezone
from datetime import timedelta

from auth_service.models import Utilisateur, Role
from appels_service.models import AppelOffres
from evaluations_service.models import (
    ComissionEvaluation, MembresCommissionEvaluation,
    RegistreReception, AssignationCT,
)
from soumissions_app.models import Soumission

# ── WIPE ──────────────────────────────────────────────────────────────────────

from evaluations_service.models import (
    SeanceOuverture, PliOuverture, ProcesVerbal, SignaturePV,
    ConformiteOffer, CapacitesOffer, EvalTechniqueOffer,
    EvalFinanciereOffer, ClassementEntry, SCDecision,
    RegistreIntegriteConfirmation, AssignationCT, RapportCT,
)
from soumissions_app.models import SoumissionEvaluateur

SCDecision.objects.all().delete()
SignaturePV.objects.all().delete()
ProcesVerbal.objects.all().delete()
ClassementEntry.objects.all().delete()
EvalFinanciereOffer.objects.all().delete()
EvalTechniqueOffer.objects.all().delete()
CapacitesOffer.objects.all().delete()
ConformiteOffer.objects.all().delete()
PliOuverture.objects.all().delete()
SeanceOuverture.objects.all().delete()
RegistreIntegriteConfirmation.objects.all().delete()
RapportCT.objects.all().delete()
AssignationCT.objects.all().delete()
RegistreReception.objects.all().delete()
MembresCommissionEvaluation.objects.all().delete()
SoumissionEvaluateur.objects.all().delete()
Soumission.objects.all().delete()
AppelOffres.objects.all().delete()
ComissionEvaluation.objects.all().delete()
Utilisateur.objects.filter(email__endswith='@test.dz').delete()
print("DB wiped")

# ── USERS ─────────────────────────────────────────────────────────────────────

def make_user(email, role_nom):
    role = Role.objects.get(nom_role=role_nom)
    u = Utilisateur.objects.create(
        email=email,
        id_role=role,
        id_membre=uuid.uuid4(),
        is_active=True,
        must_change_password=False,
    )
    u.set_password('Test1234!')
    u.save()
    print(f"  {email} [{role_nom}] id={u.id_utilisateur}")
    return u

print("Creating users...")
sc  = make_user('sc@test.dz',  'RESP_SC')
oe1 = make_user('oe1@test.dz', 'RESP_OE')
oe2 = make_user('oe2@test.dz', 'RESP_OE')
oe3 = make_user('oe3@test.dz', 'RESP_OE')
ev1 = make_user('ev1@test.dz', 'EVALUATEUR')
ev2 = make_user('ev2@test.dz', 'EVALUATEUR')
ev3 = make_user('ev3@test.dz', 'EVALUATEUR')
ct  = make_user('ct@test.dz',  'MEMBRE_COMITE_TECHNIQUE')

# ── APPEL D'OFFRES ────────────────────────────────────────────────────────────

print("Creating appel d'offres...")
now = timezone.now()
appel = AppelOffres.objects.create(
    id_service_contractant=sc.id_utilisateur,
    reference='AO-2026-001',
    titre='Travaux infrastructure test',
    description='Appel test complet COPEO',
    type_procedure='publique',
    type_prestation='travaux',
    visibilite='public',
    wilaya='Alger',
    secteur='BTP',
    montant_estime=15000000,
    date_publication=now - timedelta(days=40),
    date_limite_soumission=now - timedelta(days=10),
    date_ouverture_plis=now - timedelta(days=7),
    poids_technique=60,
    poids_financier=40,
    seuil_technique=70,
    methodology='weighted',
    statut='valide',
    etat_execution='depot_cloture',
)
print(f"  AppelOffres id={appel.id_appel_offres} ref={appel.reference}")

# ── COMMISSION ────────────────────────────────────────────────────────────────

print("Creating commission...")
commission = ComissionEvaluation.objects.create(
    id_service=sc.id_utilisateur,
    nom_comission=f'COPEO {appel.reference}',
    categorie='Travaux',
)
appel.commission_id = str(commission.id_comission)
appel.save()
print(f"  Commission id={commission.id_comission} linked to appel {appel.id_appel_offres}")

MembresCommissionEvaluation.objects.create(id_comission=commission, id_utilisateur=ev1.id_utilisateur, role_label='president')
MembresCommissionEvaluation.objects.create(id_comission=commission, id_utilisateur=ev2.id_utilisateur, role_label='membre')
MembresCommissionEvaluation.objects.create(id_comission=commission, id_utilisateur=ev3.id_utilisateur, role_label='membre')
print("  3 membres COPEO linked")

# ── COMITE TECHNIQUE ──────────────────────────────────────────────────────────

AssignationCT.objects.create(id_comission=commission, id_utilisateur=ct.id_utilisateur)
print(f"  CT assigned: {ct.email} id={ct.id_utilisateur}")

# ── SOUMISSIONS ───────────────────────────────────────────────────────────────

print("Creating soumissions...")
OES = [
    (oe1, 'Entreprise Alpha', 12500000),
    (oe2, 'Entreprise Beta',   9800000),
    (oe3, 'Entreprise Gamma', 11200000),
]
soumissions = []
for i, (oe, nom, montant) in enumerate(OES, start=1):
    s = Soumission.objects.create(
        id_appel_offre=appel.id_appel_offres,
        id_soumissionnaire=oe.id_utilisateur,
        offre_financiere_chiffree_url=f'http://localhost/fake/offre{i}.pdf',
        cle_dechiffrement_hash=f'fakehash{i:03d}',
        document_ids=[],
        statut='EN_EVALUATION',
        montant_financier=montant,
        date_soumission=now - timedelta(days=11),
    )
    soumissions.append((s, nom, montant))
    print(f"  Soumission id={s.id_soumission} {nom} {montant} DA")

# ── REGISTRE ──────────────────────────────────────────────────────────────────

print("Creating registre...")
for idx, (s, nom, _) in enumerate(soumissions, start=1):
    RegistreReception.objects.create(
        id_comission=commission,
        id_soumission=s.id_soumission,
        numero_ordre=idx,
        nom_oe=nom,
        received_at=now - timedelta(days=10),
        submitted_at=now - timedelta(days=11),
        hors_delai=False,
    )
print("  Registre seeded")

# ── SUMMARY ───────────────────────────────────────────────────────────────────

print()
print("=" * 55)
print("CREDENTIALS — password: Test1234!")
print(f"  SC      → sc@test.dz")
print(f"  COPEO1  → ev1@test.dz  (président)  id={ev1.id_utilisateur}")
print(f"  COPEO2  → ev2@test.dz  (membre)     id={ev2.id_utilisateur}")
print(f"  COPEO3  → ev3@test.dz  (membre)     id={ev3.id_utilisateur}")
print(f"  CT      → ct@test.dz               id={ct.id_utilisateur}")
print(f"  OE1     → oe1@test.dz  (Entreprise Alpha)")
print(f"  OE2     → oe2@test.dz  (Entreprise Beta)")
print(f"  OE3     → oe3@test.dz  (Entreprise Gamma)")
print(f"  commission.id = {commission.id_comission}")
print(f"  appel.id      = {appel.id_appel_offres}")
for s, nom, _ in soumissions:
    print(f"  {nom}: soumission id={s.id_soumission}")
print("=" * 55)
print("Login as ev1@test.dz to start the COPEO flow")
print("Login as ct@test.dz  to submit the CT rapport")