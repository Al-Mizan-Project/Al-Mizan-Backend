from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

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

        if options["flush"]:
            deleted, _ = Notification.objects.filter(utilisateur_id=user.id_utilisateur).delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} notifications for user {user.id_utilisateur}."))

        now = timezone.now()
        templates = [
            {
                "type_notification": "alerte",
                "titre": "Date limite proche",
                "message": "Un appel d'offres arrive a echeance dans 48 heures.",
                "priorite": "haute",
                "categorie": "rappel",
                "entite_liee_type": "appel_offre",
                "entite_liee_id": 1,
                "statut": "envoyee",
                "read_at": None,
            },
            {
                "type_notification": "information",
                "titre": "Nouveau document publie",
                "message": "Un addendum est disponible sur un appel d'offres suivi.",
                "priorite": "normale",
                "categorie": "document",
                "entite_liee_type": "document",
                "entite_liee_id": 101,
                "statut": "envoyee",
                "read_at": None,
            },
            {
                "type_notification": "attribution",
                "titre": "Marche attribue",
                "message": "Le resultat de la consultation AO-2026-001 est disponible.",
                "priorite": "normale",
                "categorie": "attribution",
                "entite_liee_type": "appel_offre",
                "entite_liee_id": 1,
                "statut": "lue",
                "read_at": now,
            },
        ]

        created = 0
        updated = 0
        for idx in range(count):
            template = templates[idx % len(templates)]
            suffix = idx + 1
            titre = f"{template['titre']} #{suffix}"
            defaults = {
                "utilisateur_id": user.id_utilisateur,
                "type_notification": template["type_notification"],
                "message": template["message"],
                "priorite": template["priorite"],
                "categorie": template["categorie"],
                "entite_liee_type": template["entite_liee_type"],
                "entite_liee_id": template["entite_liee_id"],
                "statut": template["statut"],
                "sent_at": now,
                "read_at": template["read_at"],
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
                    f"User={user.id_utilisateur} ({user.email})"
                )
            )
        )

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
