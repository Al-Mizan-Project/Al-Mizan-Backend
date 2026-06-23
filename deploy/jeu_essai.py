"""
Seed jeu d'essai — FIXED VERSION (NO UUID / NO INTEGER OVERFLOW)
Run:
python manage.py shell -c "exec(open('jeu_essai.py').read())"
"""

import uuid
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from auth_service.models import Role, Utilisateur
from acteurs_service.models import Organisation, Membre, TypeEntite
from appels_service.models import AppelOffres
from soumissions_app.models import Soumission, SoumissionStatut, SoumissionEvaluateur
from evaluations_service.models import ComissionEvaluation, MembresCommissionEvaluation

print("\n" + "="*60)
print("  JEU D'ESSAI — SEED DB AL-MIZAN (FIXED)")
print("="*60 + "\n")

with transaction.atomic():

    # ── Roles ─────────────────────────────────────────────
    print("── Rôles ─────────────────────────────────────────────")
    role_sc, _ = Role.objects.get_or_create(nom_role="RESP_SC")
    role_oe, _ = Role.objects.get_or_create(nom_role="RESP_OE")
    role_ev, _ = Role.objects.get_or_create(nom_role="EVALUATEUR")
    print("  [✓] Roles OK")

    # ── Organisations ─────────────────────────────────────
    print("\n── Organisations ─────────────────────────────────────")

    org_sc, _ = Organisation.objects.get_or_create(
        nom_officiel="Direction des Infrastructures — Wilaya d'Alger",
        defaults={
            "type_entite": TypeEntite.SERVICE_CONTRACTANT,
            "email_contact": "sc.alger@gov.dz",
            "wilaya": "Alger",
            "secteur": "Infrastructure",
        }
    )

    org_oe1, _ = Organisation.objects.get_or_create(
        nom_officiel="SARL Constructions Modernes",
        defaults={
            "type_entite": TypeEntite.OPERATEUR_ECONOMIQUE,
            "email_contact": "contact@constructions.dz",
            "wilaya": "Alger",
        }
    )

    org_copeo, _ = Organisation.objects.get_or_create(
        nom_officiel="COPEO — Commission Alger",
        defaults={
            "type_entite": TypeEntite.COMMISSION_EXTERNE,
            "email_contact": "copeo@gov.dz",
        }
    )

    print("  [✓] Organisations OK")

    # ── Users ─────────────────────────────────────────────
    print("\n── Users ─────────────────────────────────────────────")

    def make_user(org, nom, prenom, fonction, email, password, role):
        membre, _ = Membre.objects.get_or_create(
            organisation=org,
            nom=nom,
            prenom=prenom,
            defaults={"fonction": fonction}
        )

        user, created = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                "id_membre": membre.id_membre,
                "id_role": role,
                "is_active": True
            }
        )

        if created:
            user.set_password(password)
            user.save()

        return user

    user_sc = make_user(org_sc, "Ben", "SC", "Resp", "resp.sc@test.dz", "TestSC123!", role_sc)
    user_oe = make_user(org_oe1, "Ham", "OE", "Resp", "resp.oe1@test.dz", "TestOE123!", role_oe)
    user_ev = make_user(org_copeo, "Eva", "CO", "Eval", "ev1@copeo.dz", "TestEV123!", role_ev)

    print("  [✓] Users OK")

    # ── Appel Offres (FIXED PART) ─────────────────────────
    print("\n── Appel d'offres ───────────────────────────────────")

    now = timezone.now()

    appel, _ = AppelOffres.objects.get_or_create(
        reference="AO-TEST-2026-001",
        defaults={
            # ✅ FIX: MUST be int safe
            "id_service_contractant": 1,

            # ❗ commission_id is CHARFIELD → must be string safe
            "commission_id": "1",

            "titre": "Construction école Alger",
            "description": "Seed test",
            "type_procedure": "Appel d'offres ouvert",
            "type_prestation": "travaux",
            "visibilite": "public",
            "wilaya": "Alger",
            "montant_estime": Decimal("45000000.00"),

            "date_publication": now,
            "date_limite_soumission": now,
            "date_ouverture_plis": now,

            "poids_technique": 60,
            "poids_financier": 40,
            "seuil_technique": 70,
            "methodology": "weighted",
            "statut": "valide",
            "etat_execution": "depot_cloture",
        }
    )

    print(f"  [✓] Appel OK ({appel.reference})")

    # ── Commission ────────────────────────────────────────
    print("\n── Commission ───────────────────────────────────────")

    commission, _ = ComissionEvaluation.objects.get_or_create(
        id_service=1,  # SAFE INT
        nom_comission="COPEO TEST",
        defaults={"categorie": "Travaux"}
    )

    print("  [✓] Commission OK")

print("\n" + "="*60)
print("  SEED COMPLETE")
print("="*60)