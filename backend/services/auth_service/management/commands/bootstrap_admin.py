import os
import uuid

from django.core.management.base import BaseCommand, CommandError

from auth_service.models import Role, Utilisateur
from auth_service.rbac import normalize_role_name


def as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Bootstrap initial admin user from environment variables"

    def handle(self, *args, **options):
        enabled = as_bool(os.getenv("INITIAL_ADMIN_ENABLED", "false"))
        if not enabled:
            self.stdout.write("Initial admin bootstrap disabled")
            return

        email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        role_name = normalize_role_name(os.getenv("INITIAL_ADMIN_ROLE", "ADMIN"))
        membre_id_raw = os.getenv("INITIAL_ADMIN_MEMBRE_ID", "1").strip()

        if not email:
            raise CommandError("INITIAL_ADMIN_EMAIL is required when INITIAL_ADMIN_ENABLED=true")
        if not password:
            raise CommandError("INITIAL_ADMIN_PASSWORD is required when INITIAL_ADMIN_ENABLED=true")
        if not role_name:
            raise CommandError("INITIAL_ADMIN_ROLE must not be empty")
        try:
            membre_id = int(membre_id_raw)
        except ValueError as exc:
            raise CommandError("INITIAL_ADMIN_MEMBRE_ID must be an integer") from exc
        if membre_id < 1:
            raise CommandError("INITIAL_ADMIN_MEMBRE_ID must be >= 1")

        role, _ = Role.objects.get_or_create(nom_role=role_name)
        user, _ = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                "id_role": role,
                "id_membre": membre_id,
            },
        )
        user.id_role = role
        user.id_membre = membre_id
        user.set_password(password)
        user.is_active = True
        user.must_change_password = False
        user.save(update_fields=["id_role", "id_membre", "password", "is_active", "must_change_password", "updated_at"])
        self.stdout.write(f"Initial admin ready: {email}")
