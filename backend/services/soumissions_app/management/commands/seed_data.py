from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from appels_service.models import AppelOffres
from auth_service.models import Role, Utilisateur
from soumissions_app.models import Soumission, SoumissionStatut


DEFAULT_SEED_EMAIL = "c@a.dz"
DEFAULT_SEED_PASSWORD = "test1234"


class Command(BaseCommand):
    help = "Generate deterministic test data for soumissions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all soumissions before seeding",
        )
        parser.add_argument(
            "--soumissionnaire-id",
            type=int,
            default=None,
            help="Use an existing auth user id as soumissionnaire",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of soumissions to seed (default: 5)",
        )

    def handle(self, *args, **options):
        flush = options["flush"]
        count = max(1, int(options["count"]))

        if flush:
            deleted, _ = Soumission.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing soumission rows."))

        soumissionnaire = self._resolve_soumissionnaire(options.get("soumissionnaire_id"))
        appel_ids = self._resolve_appel_ids(count)

        statuts = [
            SoumissionStatut.SOUMIS,
            SoumissionStatut.EN_OUVERTURE,
            SoumissionStatut.EN_EVALUATION,
            SoumissionStatut.EVALU_TERMINEE,
            SoumissionStatut.RETRAITE,
        ]

        created = 0
        updated = 0
        for idx, appel_id in enumerate(appel_ids, start=1):
            statut = statuts[(idx - 1) % len(statuts)]
            default_montant = Decimal("500000.00") + Decimal(idx * 150000)
            montant = default_montant if statut in {SoumissionStatut.EN_EVALUATION, SoumissionStatut.EVALU_TERMINEE} else None

            payload = {
                "offre_financiere_chiffree_url": (
                    f"http://minio/almizan-documents/seed-soumission-{soumissionnaire.id_utilisateur}-{appel_id}.pdf.enc"
                ),
                "cle_dechiffrement_hash": f"seed_encrypted_aes_key_{soumissionnaire.id_utilisateur}_{appel_id}",
                "document_ids": [100 + idx, 200 + idx],
                "statut": statut,
                "montant_financier": montant,
                "conformite_statut": "CONFORME" if idx % 2 == 0 else "A_VERIFIER",
                "conformite_rapport": "Seed data generated for integration testing",
            }

            soumission, was_created = Soumission.objects.update_or_create(
                id_appel_offre=appel_id,
                id_soumissionnaire=soumissionnaire.id_utilisateur,
                defaults=payload,
            )

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created soumission #{soumission.id_soumission} for AO {appel_id}"))
            else:
                updated += 1
                self.stdout.write(f"Updated soumission #{soumission.id_soumission} for AO {appel_id}")

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Soumissions seed completed. Created={created}, Updated={updated}, "
                    f"Soumissionnaire={soumissionnaire.id_utilisateur} ({soumissionnaire.email})"
                )
            )
        )

    def _resolve_soumissionnaire(self, explicit_user_id):
        if explicit_user_id is not None:
            user = Utilisateur.objects.filter(id_utilisateur=explicit_user_id).first()
            if not user:
                raise CommandError(f"No Utilisateur found with id {explicit_user_id}")
            return user

        existing = Utilisateur.objects.select_related("id_role").order_by("id_utilisateur").first()
        if existing:
            return existing

        role, _ = Role.objects.get_or_create(nom_role="admin")
        user = Utilisateur.objects.filter(email=DEFAULT_SEED_EMAIL).first()
        if not user:
            user = Utilisateur(
                id_role=role,
                id_membre=1,
                email=DEFAULT_SEED_EMAIL,
            )
            user.set_password(DEFAULT_SEED_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created fallback seed user {DEFAULT_SEED_EMAIL}"))
        return user

    def _resolve_appel_ids(self, count):
        appel_ids = list(
            AppelOffres.objects.order_by("id_appel_offres").values_list("id_appel_offres", flat=True)[:count]
        )
        if appel_ids:
            return appel_ids

        self.stdout.write(
            self.style.WARNING(
                "No appels-offres found; using synthetic appel ids. "
                "Run seed_appels first for fully linked test data."
            )
        )
        return [100 + i for i in range(1, count + 1)]
