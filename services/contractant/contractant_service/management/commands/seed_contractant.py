"""
Seed the contractant database with sample data.

Usage:
    python manage.py seed_contractant              # insert only
    python manage.py seed_contractant --flush      # drop all existing data first
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from contractant_service.models import (
    CommissionEvaluation,
    CommissionExterne,
    CommissionInterne,
    MembresCommissionEvaluation,
    MembresCommissionInterne,
    ServiceContractant,
)


SERVICES = [
    {
        "id_tutelle": 1,
        "categorie": "Ministère",
        "code_ordonnateur": "ORD-001",
    },
    {
        "id_tutelle": 2,
        "categorie": "Wilaya",
        "code_ordonnateur": "ORD-002",
    },
    {
        "id_tutelle": 1,
        "categorie": "Commune",
        "code_ordonnateur": "ORD-003",
    },
]

COMMISSIONS_EVAL = [
    # (service_index, nom, categorie)
    (0, "Commission ouverture plis - Lot 1", "Travaux"),
    (0, "Commission analyse technique", "Fournitures"),
    (1, "Commission d'évaluation wilaya", "Services"),
    (2, "Commission locale", "Travaux"),
]

COMMISSIONS_INTERNES = [
    # (service_index, nom, type)
    (0, "Commission interne permanente", "parmanante"),
    (0, "Commission ad-hoc urgence", "adhoc"),
    (1, "Commission sectorielle", "parmanante"),
    (2, "Commission communale adhoc", "adhoc"),
]

COMMISSIONS_EXTERNES = [
    {
        "nom_comission": "Commission nationale des marchés",
        "niveau_competance": "Nationale",
        "seuils_competence_financiere": "Au-dessus de 500 000 000 DZD",
    },
    {
        "nom_comission": "Commission sectorielle des marchés",
        "niveau_competance": "Sectorielle",
        "seuils_competence_financiere": "Entre 100 000 000 et 500 000 000 DZD",
    },
    {
        "nom_comission": "Commission de wilaya",
        "niveau_competance": "de Wilaya",
        "seuils_competence_financiere": "Entre 10 000 000 et 100 000 000 DZD",
    },
    {
        "nom_comission": "Commission communale",
        "niveau_competance": "Communale",
        "seuils_competence_financiere": "Moins de 10 000 000 DZD",
    },
]

# Fake id_membre values (cross-service refs — no real rows in this DB)
EVAL_MEMBRES = [
    # (commission_eval_index, id_membre)
    (0, 1), (0, 2), (0, 3),
    (1, 2), (1, 4),
    (2, 5), (2, 6),
    (3, 7),
]

INTERNE_MEMBRES = [
    # (commission_interne_index, id_membre)
    (0, 1), (0, 2),
    (1, 3),
    (2, 4), (2, 5),
    (3, 6),
]


class Command(BaseCommand):
    help = "Seed the contractant database with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing data...")
            MembresCommissionInterne.objects.all().delete()
            MembresCommissionEvaluation.objects.all().delete()
            CommissionInterne.objects.all().delete()
            CommissionEvaluation.objects.all().delete()
            CommissionExterne.objects.all().delete()
            ServiceContractant.objects.all().delete()
            self.stdout.write(self.style.WARNING("All contractant data deleted."))

        # ── Services contractants ────────────────────────────────────
        services = []
        for data in SERVICES:
            svc, created = ServiceContractant.objects.get_or_create(
                code_ordonnateur=data["code_ordonnateur"],
                defaults={
                    "id_tutelle": data["id_tutelle"],
                    "categorie": data["categorie"],
                },
            )
            services.append(svc)
            flag = "created" if created else "exists"
            self.stdout.write(f"  ServiceContractant [{svc.id_service}] {svc.code_ordonnateur} — {flag}")

        # ── Commissions évaluation ───────────────────────────────────
        comms_eval = []
        for svc_idx, nom, categorie in COMMISSIONS_EVAL:
            ce, created = CommissionEvaluation.objects.get_or_create(
                id_service=services[svc_idx],
                nom_comission=nom,
                defaults={"categorie": categorie},
            )
            comms_eval.append(ce)
            flag = "created" if created else "exists"
            self.stdout.write(f"  CommissionEvaluation [{ce.id_comission}] {nom} — {flag}")

        # ── Commissions internes ─────────────────────────────────────
        comms_interne = []
        for svc_idx, nom, type_c in COMMISSIONS_INTERNES:
            ci, created = CommissionInterne.objects.get_or_create(
                id_service=services[svc_idx],
                nom_comission=nom,
                defaults={"type_comission": type_c},
            )
            comms_interne.append(ci)
            flag = "created" if created else "exists"
            self.stdout.write(f"  CommissionInterne [{ci.id_comission_interne}] {nom} — {flag}")

        # ── Commissions externes ─────────────────────────────────────
        for data in COMMISSIONS_EXTERNES:
            ce, created = CommissionExterne.objects.get_or_create(
                nom_comission=data["nom_comission"],
                defaults={
                    "niveau_competance": data["niveau_competance"],
                    "seuils_competence_financiere": data["seuils_competence_financiere"],
                },
            )
            flag = "created" if created else "exists"
            self.stdout.write(f"  CommissionExterne [{ce.id_comission_externe}] {ce.nom_comission} — {flag}")

        # ── Membres commission évaluation ────────────────────────────
        for ce_idx, id_membre in EVAL_MEMBRES:
            obj, created = MembresCommissionEvaluation.objects.get_or_create(
                id_comission=comms_eval[ce_idx],
                id_membre=id_membre,
            )
            flag = "created" if created else "exists"
            self.stdout.write(
                f"  MembresCommEval [ce={comms_eval[ce_idx].id_comission} | membre={id_membre}] — {flag}"
            )

        # ── Membres commission interne ───────────────────────────────
        for ci_idx, id_membre in INTERNE_MEMBRES:
            obj, created = MembresCommissionInterne.objects.get_or_create(
                id_commision_interne=comms_interne[ci_idx],
                id_membre=id_membre,
            )
            flag = "created" if created else "exists"
            self.stdout.write(
                f"  MembresCommInterne [ci={comms_interne[ci_idx].id_comission_interne} | membre={id_membre}] — {flag}"
            )

        self.stdout.write(self.style.SUCCESS("\nSeed completed successfully."))
