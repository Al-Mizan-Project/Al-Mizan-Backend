from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from appels_service.models import AppelOffres, AppelOffresSuivi
from auth_service.models import Utilisateur
from notifications_service.models import Notification


DEFAULT_USER_EMAIL = "c@a.dz"


class Command(BaseCommand):
    help = "Seed deterministic notifications for one user"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete target user notifications first")
        parser.add_argument("--user-id", type=int, default=None, help="Target user id")
        parser.add_argument("--user-email", default=DEFAULT_USER_EMAIL, help="Fallback target user email")
        parser.add_argument("--count", type=int, default=6, help="Number of notifications to seed")

    def handle(self, *args, **options):
        user = self._resolve_user(options.get("user_id"), options.get("user_email"))
        count = max(1, int(options["count"]))
        linked_appels = self._select_appels_for_notifications(user_id=user.id_utilisateur, count=count)

        if options["flush"]:
            deleted, _ = Notification.objects.filter(utilisateur_id=user.id_utilisateur).delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} notifications for user {user.id_utilisateur}."))

        now = timezone.now()
        templates = [
            {
                "type_notification": "alerte",
                "titre": "Date limite proche",
                "message": "Date limite proche pour {reference}.",
                "priorite": "haute",
                "categorie": "rappel",
                "read": False,
            },
            {
                "type_notification": "information",
                "titre": "Nouveau document publie",
                "message": "Un document a ete publie pour {reference}.",
                "priorite": "normale",
                "categorie": "document",
                "read": False,
            },
            {
                "type_notification": "attribution",
                "titre": "Marche attribue",
                "message": "Le resultat de la consultation {reference} est disponible.",
                "priorite": "normale",
                "categorie": "attribution",
                "read": True,
            },
        ]

        created = 0
        updated = 0
        for idx in range(count):
            template = templates[idx % len(templates)]
            appel = linked_appels[idx]
            suffix = idx + 1
            reference = appel.reference or f"AO-{appel.id_appel_offres}"
            titre = f"{template['titre']} - {reference} #{suffix}"
            is_read = bool(template["read"])
            defaults = {
                "utilisateur_id": user.id_utilisateur,
                "type_notification": template["type_notification"],
                "message": template["message"].format(reference=reference),
                "priorite": template["priorite"],
                "categorie": template["categorie"],
                "entite_liee_type": "appel_offre",
                "entite_liee_id": appel.id_appel_offres,
                "statut": "lue" if is_read else "envoyee",
                "sent_at": now,
                "read_at": now if is_read else None,
            }

            notification, was_created = Notification.objects.update_or_create(
                utilisateur_id=user.id_utilisateur,
                titre=titre,
                defaults=defaults,
            )

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created notification {notification.id}: {notification.titre}"))
            else:
                updated += 1
                self.stdout.write(f"Updated notification {notification.id}: {notification.titre}")

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Notifications seed completed. Created={created}, Updated={updated}, "
                    f"User={user.id_utilisateur} ({user.email}), "
                    f"LinkedAppels={sorted({a.id_appel_offres for a in linked_appels})}"
                )
            )
        )

    def _select_appels_for_notifications(self, user_id, count):
        watched_ids = list(
            AppelOffresSuivi.objects.filter(id_utilisateur=user_id)
            .order_by("id")
            .values_list("id_appel_offres_id", flat=True)
        )

        watched_appels = list(
            AppelOffres.objects.filter(id_appel_offres__in=watched_ids).order_by("id_appel_offres")
        )
        remaining_appels = list(
            AppelOffres.objects.exclude(id_appel_offres__in=watched_ids).order_by("id_appel_offres")
        )
        candidates = watched_appels + remaining_appels

        if not candidates:
            raise CommandError("No appels found. Run seed_appels before seed_notifications.")

        # Ensure deterministic count even when requested notifications > available appels.
        return [candidates[idx % len(candidates)] for idx in range(count)]

    def _resolve_user(self, user_id, email):
        if user_id is not None:
            user = Utilisateur.objects.filter(id_utilisateur=user_id).first()
            if not user:
                raise CommandError(f"No Utilisateur found with id {user_id}")
            return user

        user = Utilisateur.objects.filter(email=(email or "").strip().lower()).first()
        if user:
            return user

        fallback = Utilisateur.objects.order_by("id_utilisateur").first()
        if fallback:
            self.stdout.write(
                self.style.WARNING(
                    (
                        f"User {email!r} not found; using fallback user "
                        f"{fallback.id_utilisateur} ({fallback.email})."
                    )
                )
            )
            return fallback

        raise CommandError("No users found. Run seed_auth before seed_notifications.")
