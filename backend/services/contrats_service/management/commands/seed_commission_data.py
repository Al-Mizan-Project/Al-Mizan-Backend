"""
Seed commission and attribution data so commission.externe user can see dossiers.

Usage:
    python manage.py seed_commission_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.db import connection, transaction
from django.core.management.base import BaseCommand
from django.utils import timezone

from contractant_service.models import CommissionExterne, ServiceContractant
from appels_service.models import AppelOffres


class Command(BaseCommand):
    help = "Seed commission and attribution data for commission.externe user"

    @transaction.atomic
    def handle(self, *args, **options):
        # ── 1. ServiceContractant (id_service=1 to match appels_offres) ──
        svc, created = ServiceContractant.objects.get_or_create(
            id_service=1,
            defaults={"id_tutelle": 1, "categorie": "Ministère", "code_ordonnateur": "ORD-001"},
        )
        self.stdout.write(f"  ServiceContractant [id={svc.id_service}] — {'created' if created else 'exists'}")

        # ── 2. CommissionExterne ──
        ce, created = CommissionExterne.objects.get_or_create(
            nom_comission="Commission nationale des marchés",
            defaults={
                "niveau_competance": "Nationale",
                "seuils_competence_financiere": "Tous seuils",
            },
        )
        self.stdout.write(
            f"  CommissionExterne [id={ce.id_comission_externe}] {ce.nom_comission} — {'created' if created else 'exists'}"
        )
        commission_id_int = ce.id_comission_externe

        # ── 3. MembresCommissionExterne (link user id_membre=3 to commission) ──
        # Use raw SQL because Django model has UUIDField but DB column is integer
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO "Membres_Commission_Externe" (id_membre, id_comission_externe)
                VALUES (%s, %s)
                ON CONFLICT (id_membre, id_comission_externe) DO NOTHING
                RETURNING id
                """,
                [3, commission_id_int],
            )
            row = cursor.fetchone()
            created = row is not None
        self.stdout.write(
            f"  MembresCommissionExterne [membre=3 -> commission={commission_id_int}] — {'created' if created else 'exists'}"
        )

        # ── 4. Attributions for soumissions of AO#1 (raw SQL due to model-DB type mismatches) ──
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_soumission FROM soumissions WHERE id_appel_offre = %s", [1])
            soumission_ids = [row[0] for row in cursor.fetchall()]
        self.stdout.write(f"  Found {len(soumission_ids)} soumissions for appel_offre=1")

        created_count = 0
        now = timezone.now()
        for sid in soumission_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM attribution WHERE soumission_id = %s AND commission_id = %s",
                    [sid, commission_id_int],
                )
                if cursor.fetchone():
                    continue
                cursor.execute(
                    """
                    INSERT INTO attribution (service_contractant_id, soumission_id, appel_id, commission_id,
                                             validated_by, validation_level, statut, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [1, sid, 1, commission_id_int, None, 'externe_nationale', 'provisoire', now, now],
                )
                created_count += 1
                self.stdout.write(f"    Attribution [soumission={sid} -> commission={commission_id_int}]")

        self.stdout.write(f"  Created {created_count} new attributions")

        # ── 5. Update appels_offres.commission_id ──
        updated = AppelOffres.objects.filter(id_appel_offres=1).update(commission_id=commission_id_int)
        self.stdout.write(f"  Updated AppelOffres[1].commission_id -> {commission_id_int} (rows={updated})")

        self.stdout.write(self.style.SUCCESS("\nSeed completed successfully."))
