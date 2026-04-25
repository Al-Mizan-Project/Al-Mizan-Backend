"""
Seed the appels database with sample data.

Usage:
    python manage.py seed_appels              # insert only
    python manage.py seed_appels --flush      # drop all existing data first
"""
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from appels_service.models import AppelOffres, DocumentsAppel


APPELS = [
    {
        "id_service_contractant": 1,
        "reference": "AO-2026-001",
        "titre": "Fourniture de matériel informatique",
        "description": "Acquisition de postes de travail et périphériques pour les directions.",
        "type_procedure": "Appel d'offres ouvert",
        "montant_estime": "15000000.00",
        "poids_technique": 40,
        "poids_financier": 60,
        "statut": "publie",
    },
    {
        "id_service_contractant": 1,
        "reference": "AO-2026-002",
        "titre": "Travaux de réhabilitation du siège",
        "description": "Rénovation des locaux administratifs.",
        "type_procedure": "Appel d'offres restreint",
        "montant_estime": "85000000.00",
        "poids_technique": 60,
        "poids_financier": 40,
        "statut": "brouillon",
    },
    {
        "id_service_contractant": 2,
        "reference": "AO-2026-003",
        "titre": "Prestation de services de gardiennage",
        "description": "Surveillance et sécurité des bâtiments.",
        "type_procedure": "Consultation",
        "montant_estime": "5400000.00",
        "poids_technique": 50,
        "poids_financier": 50,
        "statut": "depot_cloture",
    },
    {
        "id_service_contractant": 2,
        "reference": "AO-2026-004",
        "titre": "Acquisition de véhicules de service",
        "description": "Achat de véhicules pour le parc automobile.",
        "type_procedure": "Appel d'offres ouvert",
        "montant_estime": "32000000.00",
        "poids_technique": 30,
        "poids_financier": 70,
        "statut": "plis_ouverts",
    },
    {
        "id_service_contractant": 3,
        "reference": "AO-2026-005",
        "titre": "Fourniture de produits de nettoyage",
        "description": "Produits d'entretien pour les locaux.",
        "type_procedure": "Consultation",
        "montant_estime": "1200000.00",
        "poids_technique": 50,
        "poids_financier": 50,
        "statut": "annule",
    },
]

# Fake document IDs (cross-service refs)
DOCUMENTS = [
    # (appel_index, id_document)
    (0, 101),
    (0, 102),
    (1, 103),
    (2, 104),
    (3, 105),
    (3, 106),
]


class Command(BaseCommand):
    help = "Seed the appels database with sample data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            DocumentsAppel.objects.all().delete()
            AppelOffres.objects.all().delete()
            sequence_sql = connection.ops.sequence_reset_sql(
                no_style(),
                [AppelOffres, DocumentsAppel],
            )
            with connection.cursor() as cursor:
                for sql in sequence_sql:
                    cursor.execute(sql)
            self.stdout.write(self.style.WARNING("Flushed all appels data."))

        now = timezone.now()
        future_deadline = now + timedelta(days=30)
        appel_objects = []
        for data in APPELS:
            obj, created = AppelOffres.objects.get_or_create(
                reference=data["reference"],
                defaults={
                    **data,
                    "date_publication": now if data["statut"] != "brouillon" else None,
                    "date_limite_soumission": future_deadline if data["statut"] not in ("brouillon",) else None,
                    "date_ouverture_plis": now if data["statut"] in ("plis_ouverts",) else None,
                },
            )
            appel_objects.append(obj)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created AppelOffres: {obj.reference}"))
            else:
                self.stdout.write(f"  Skipped (exists): {obj.reference}")

        for appel_idx, doc_id in DOCUMENTS:
            appel = appel_objects[appel_idx]
            link, created = DocumentsAppel.objects.get_or_create(
                id_appel_offres=appel,
                id_document=doc_id,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Linked document {doc_id} -> appel {appel.reference}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
