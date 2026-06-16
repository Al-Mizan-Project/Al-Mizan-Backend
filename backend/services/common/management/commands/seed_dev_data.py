from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from acteurs_service.models import Membre
from appels_service.models import AppelOffres, AppelOffresSuivi
from auth_service.models import Utilisateur


DEFAULT_ADMIN_EMAIL = "a@a.dz"
DEFAULT_ADMIN_PASSWORD = "admin1234"
DEFAULT_CONTRACTANT_EMAIL = "c@a.dz"
DEFAULT_CONTRACTANT_PASSWORD = "test1234"
DEFAULT_LEGACY_CONTRACTANT_EMAIL = "contractant.demo@almizan.local"
DEFAULT_LEGACY_CONTRACTANT_PASSWORD = "ContractantPass123!"


class Command(BaseCommand):
    help = "Seed coherent dev data across auth, contractant, appels, soumissions and notifications"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Flush seedable data before insert")
        parser.add_argument("--with-documents", action="store_true", help="Also run seed_documents (requires MinIO)")
        parser.add_argument("--soumissions-count", type=int, default=5, help="How many soumissions to seed")
        parser.add_argument("--notifications-count", type=int, default=6, help="How many notifications to seed")
        parser.add_argument("--watched-count", type=int, default=3, help="How many appels to mark as watched for contractant")
        parser.add_argument("--admin-email", default=DEFAULT_ADMIN_EMAIL, help="Admin email")
        parser.add_argument("--admin-password", default=DEFAULT_ADMIN_PASSWORD, help="Admin password")
        parser.add_argument("--contractant-email", default=DEFAULT_CONTRACTANT_EMAIL, help="Contractant email")
        parser.add_argument("--contractant-password", default=DEFAULT_CONTRACTANT_PASSWORD, help="Contractant password")
        parser.add_argument(
            "--legacy-contractant-email",
            default=DEFAULT_LEGACY_CONTRACTANT_EMAIL,
            help="Legacy contractant email (set empty to disable)",
        )
        parser.add_argument(
            "--legacy-contractant-password",
            default=DEFAULT_LEGACY_CONTRACTANT_PASSWORD,
            help="Legacy contractant password",
        )
        parser.add_argument("--admin-membre-id", type=int, default=None, help="Admin id_membre (optional override)")
        parser.add_argument("--contractant-membre-id", type=int, default=None, help="Contractant id_membre (optional override)")

    def handle(self, *args, **options):
        flush = bool(options["flush"])

        self.stdout.write("Seeding acteurs service data...")
        call_command("seed_acteurs", flush=flush)

        self.stdout.write("Seeding contractant service data...")
        call_command("seed_contractant", flush=flush)

        admin_membre_id, contractant_membre_id = self._resolve_membre_ids(
            admin_override=options.get("admin_membre_id"),
            contractant_override=options.get("contractant_membre_id"),
        )

        self.stdout.write("Seeding auth users/roles/permissions...")
        call_command(
            "seed_auth",
            flush=flush,
            admin_email=options["admin_email"],
            admin_password=options["admin_password"],
            contractant_email=options["contractant_email"],
            contractant_password=options["contractant_password"],
            legacy_contractant_email=options["legacy_contractant_email"],
            legacy_contractant_password=options["legacy_contractant_password"],
            admin_membre_id=admin_membre_id,
            contractant_membre_id=contractant_membre_id,
        )

        contractant_user = Utilisateur.objects.filter(
            email=options["contractant_email"].strip().lower()
        ).first()
        if not contractant_user:
            raise CommandError("Unable to locate contractant seed user after seed_auth")

        if options["with_documents"]:
            self.stdout.write("Seeding document metadata + MinIO objects...")
            call_command(
                "seed_documents",
                flush=flush,
                operator_id=contractant_user.id_utilisateur,
            )

        self.stdout.write("Seeding appels service data...")
        call_command("seed_appels", flush=flush)

        watched_created, watched_total = self._seed_watched_appels(
            user_id=contractant_user.id_utilisateur,
            count=max(0, int(options["watched_count"])),
            flush=flush,
        )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Watched appels seeded. "
                    f"Created={watched_created}, TotalWatched={watched_total}, "
                    f"User={contractant_user.id_utilisateur} ({contractant_user.email})"
                )
            )
        )

        self.stdout.write("Seeding soumissions data...")
        call_command(
            "seed_data",
            flush=flush,
            soumissionnaire_id=contractant_user.id_utilisateur,
            count=options["soumissions_count"],
        )

        self.stdout.write("Seeding notifications data...")
        call_command(
            "seed_notifications",
            flush=flush,
            user_id=contractant_user.id_utilisateur,
            count=options["notifications_count"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Seed completed successfully. "
                    f"Admin={options['admin_email']} / {options['admin_password']} | "
                    f"Contractant={options['contractant_email']} / {options['contractant_password']}"
                )
            )
        )
        legacy_email = (options.get("legacy_contractant_email") or "").strip().lower()
        legacy_password = options.get("legacy_contractant_password") or ""
        if legacy_email and legacy_password:
            self.stdout.write(
                self.style.SUCCESS(
                    f"LegacyContractant={legacy_email} / {legacy_password}"
                )
            )

    def _resolve_membre_ids(self, admin_override, contractant_override):
        membres = list(Membre.objects.order_by("id_membre").values_list("id_membre", flat=True))
        if not membres:
            raise CommandError("No membres available after seed_acteurs")

        known = set(membres)
        admin_membre_id = admin_override if admin_override in known else membres[0]
        if admin_override is not None and admin_override not in known:
            self.stdout.write(
                self.style.WARNING(
                    f"Requested admin_membre_id={admin_override} not found; using {admin_membre_id}."
                )
            )

        if contractant_override in known:
            contractant_membre_id = contractant_override
        else:
            contractant_membre_id = membres[1] if len(membres) > 1 else admin_membre_id
            if contractant_override is not None and contractant_override not in known:
                self.stdout.write(
                    self.style.WARNING(
                        (
                            f"Requested contractant_membre_id={contractant_override} not found; "
                            f"using {contractant_membre_id}."
                        )
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Resolved membre ids: admin={admin_membre_id}, contractant={contractant_membre_id}"
            )
        )
        return admin_membre_id, contractant_membre_id

    def _seed_watched_appels(self, user_id, count, flush):
        user_watches = AppelOffresSuivi.objects.filter(id_utilisateur=user_id)
        if flush:
            user_watches.delete()

        if count <= 0:
            return 0, AppelOffresSuivi.objects.filter(id_utilisateur=user_id).count()

        selected_appels = list(
            AppelOffres.objects.filter(statut="valide", etat_execution="publie").order_by("id_appel_offres")[:count]
        )

        if len(selected_appels) < count:
            selected_ids = {appel.id_appel_offres for appel in selected_appels}
            remaining = count - len(selected_appels)
            fallback_appels = (
                AppelOffres.objects.exclude(id_appel_offres__in=selected_ids)
                .order_by("id_appel_offres")[:remaining]
            )
            selected_appels.extend(list(fallback_appels))

        created = 0
        for appel in selected_appels:
            _, was_created = AppelOffresSuivi.objects.get_or_create(
                id_appel_offres=appel,
                id_utilisateur=user_id,
            )
            if was_created:
                created += 1

        total = AppelOffresSuivi.objects.filter(id_utilisateur=user_id).count()
        return created, total
