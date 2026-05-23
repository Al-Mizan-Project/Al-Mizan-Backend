from django.core.management.base import BaseCommand
from django.db import transaction

from acteurs_service.models import CommissionExterne, Organisation, TypeEntite, NiveauCompetence


DEFAULT_COMMISSIONS = [
    {
        "nom_officiel": "Commission Nationale",
        "niveau": NiveauCompetence.NATIONAL,
        "seuil": "10000000.00",
        "wilaya": "Alger",
        "secteur": "BTP",
        "numero_agrement": "NAT-001",
        "specialite": "Generale",
    },
    {
        "nom_officiel": "Commission Sectorielle BTP",
        "niveau": NiveauCompetence.SECTORIELLE,
        "seuil": "5000000.00",
        "wilaya": "Alger",
        "secteur": "BTP",
        "numero_agrement": "SEC-001",
        "specialite": "BTP",
    },
    {
        "nom_officiel": "Commission Wilaya Alger",
        "niveau": NiveauCompetence.WILAYA,
        "seuil": "1000000.00",
        "wilaya": "Alger",
        "secteur": "BTP",
        "numero_agrement": "WIL-001",
        "specialite": "Alger",
    },
]


class Command(BaseCommand):
    help = "Seed acteurs_service commissions externes (seuils de validation)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing external commissions before insert",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            CommissionExterne.objects.all().delete()
            Organisation.objects.filter(type_entite=TypeEntite.COMMISSION_EXTERNE).delete()
            self.stdout.write(self.style.WARNING("Flushed commission externe data."))

        created = 0
        for payload in DEFAULT_COMMISSIONS:
            org, _ = Organisation.objects.update_or_create(
                nom_officiel=payload["nom_officiel"],
                defaults={
                    "type_entite": TypeEntite.COMMISSION_EXTERNE,
                    "wilaya": payload["wilaya"],
                    "secteur": payload["secteur"],
                },
            )
            org.type_entite = TypeEntite.COMMISSION_EXTERNE
            org.wilaya = payload["wilaya"]
            org.secteur = payload["secteur"]
            org.save(update_fields=["type_entite", "wilaya", "secteur"])

            _, was_created = CommissionExterne.objects.update_or_create(
                organisation=org,
                defaults={
                    "numero_agrement": payload["numero_agrement"],
                    "specialite": payload["specialite"],
                    "niveau_competence": payload["niveau"],
                    "seuil": payload["seuil"],
                },
            )
            if was_created:
                created += 1

        total = CommissionExterne.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Commission externes seeded. Created={created}, Total={total}."
            )
        )
