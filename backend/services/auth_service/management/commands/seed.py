from django.core.management.base import BaseCommand
import uuid

from auth_service.models import Permission, PermissionRole, Role, Utilisateur
from auth_service.rbac import OBSOLETE_ROLE_REPLACEMENTS, ROLE_PERMISSIONS


DEFAULT_ADMIN_EMAIL = "a@a.dz"
DEFAULT_ADMIN_PASSWORD = "admin1234"
DEFAULT_CONTRACTANT_EMAIL = "c@a.dz"
DEFAULT_CONTRACTANT_PASSWORD = "test1234"
DEFAULT_LEGACY_CONTRACTANT_EMAIL = "contractant.demo@almizan.local"
DEFAULT_LEGACY_CONTRACTANT_PASSWORD = "ContractantPass123!"

class Command(BaseCommand):
    help = "Seed auth roles, permissions and test users"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing auth users, roles and permissions first")
        parser.add_argument("--admin-email", default=DEFAULT_ADMIN_EMAIL, help="Admin email")
        parser.add_argument("--admin-password", default=DEFAULT_ADMIN_PASSWORD, help="Admin password")
        parser.add_argument("--contractant-email", default=DEFAULT_CONTRACTANT_EMAIL, help="Contractant test email")
        parser.add_argument(
            "--contractant-password",
            default=DEFAULT_CONTRACTANT_PASSWORD,
            help="Contractant test password",
        )
        parser.add_argument(
            "--legacy-contractant-email",
            default=DEFAULT_LEGACY_CONTRACTANT_EMAIL,
            help="Legacy contractant test email (set empty to disable)",
        )
        parser.add_argument(
            "--legacy-contractant-password",
            default=DEFAULT_LEGACY_CONTRACTANT_PASSWORD,
            help="Legacy contractant test password",
        )
        parser.add_argument("--admin-membre-id", type=int, default=1, help="Admin id_membre")
        parser.add_argument("--contractant-membre-id", type=int, default=2, help="Contractant id_membre")

    def handle(self, *args, **options):
        if options["flush"]:
            PermissionRole.objects.all().delete()
            Utilisateur.objects.all().delete()
            Permission.objects.all().delete()
            Role.objects.all().delete()
            self.stdout.write(self.style.WARNING("Flushed auth users, roles and permissions."))

        self._replace_obsolete_roles()
        roles = {name: Role.objects.get_or_create(nom_role=name)[0] for name in ROLE_PERMISSIONS}
        admin_role = roles["ADMIN"]
        contractant_role = roles["RESP_SC"]

        permissions = {}
        for perm_name in sorted({perm for perms in ROLE_PERMISSIONS.values() for perm in perms}):
            perm, _ = Permission.objects.get_or_create(nom_permission=perm_name)
            permissions[perm_name] = perm

        for role_name, permission_names in ROLE_PERMISSIONS.items():
            self._replace_role_permissions(roles[role_name], [permissions[name] for name in permission_names])

        admin_user, _ = Utilisateur.objects.get_or_create(
            email=options["admin_email"].strip().lower(),
            defaults={
                "id_role": admin_role,
                "id_membre": self._member_uuid(options["admin_membre_id"]),
            },
        )
        admin_user.id_role = admin_role
        admin_user.id_membre = self._member_uuid(options["admin_membre_id"])
        admin_user.is_active = True
        admin_user.must_change_password = False
        admin_user.set_password(options["admin_password"])
        admin_user.save(update_fields=["id_role", "id_membre", "is_active", "must_change_password", "password", "updated_at"])

        contractant_user, _ = Utilisateur.objects.get_or_create(
            email=options["contractant_email"].strip().lower(),
            defaults={
                "id_role": contractant_role,
                "id_membre": self._member_uuid(options["contractant_membre_id"]),
            },
        )
        contractant_user.id_role = contractant_role
        contractant_user.id_membre = self._member_uuid(options["contractant_membre_id"])
        contractant_user.is_active = True
        contractant_user.must_change_password = False
        contractant_user.set_password(options["contractant_password"])
        contractant_user.save(update_fields=["id_role", "id_membre", "is_active", "must_change_password", "password", "updated_at"])

        legacy_contractant_email = (options.get("legacy_contractant_email") or "").strip().lower()
        legacy_contractant_password = options.get("legacy_contractant_password") or ""
        legacy_contractant_user = None
        if legacy_contractant_email:
            if legacy_contractant_email in {admin_user.email, contractant_user.email}:
                self.stdout.write(
                    self.style.WARNING(
                        (
                            "Legacy contractant email matches an existing seeded account; "
                            "skipping legacy user creation."
                        )
                    )
                )
            else:
                legacy_contractant_user, _ = Utilisateur.objects.get_or_create(
                    email=legacy_contractant_email,
                    defaults={
                        "id_role": contractant_role,
                        "id_membre": self._member_uuid(options["contractant_membre_id"]),
                    },
                )
                legacy_contractant_user.id_role = contractant_role
                legacy_contractant_user.id_membre = self._member_uuid(options["contractant_membre_id"])
                legacy_contractant_user.is_active = True
                legacy_contractant_user.must_change_password = False

                update_fields = ["id_role", "id_membre", "is_active", "must_change_password", "updated_at"]
                if legacy_contractant_password:
                    legacy_contractant_user.set_password(legacy_contractant_password)
                    update_fields.append("password")

                legacy_contractant_user.save(update_fields=update_fields)

        self.stdout.write(self.style.SUCCESS(f"Admin user ready: {admin_user.email} (id={admin_user.id_utilisateur})"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Contractant user ready: {contractant_user.email} (id={contractant_user.id_utilisateur})"
            )
        )
        if legacy_contractant_user:
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Legacy contractant user ready: "
                        f"{legacy_contractant_user.email} (id={legacy_contractant_user.id_utilisateur})"
                    )
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Credentials: "
                    f"admin={options['admin_email']} / {options['admin_password']} ; "
                    f"contractant={options['contractant_email']} / {options['contractant_password']}"
                )
            )
        )
        if legacy_contractant_user and legacy_contractant_password:
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Legacy credentials: "
                        f"contractant={legacy_contractant_user.email} / {legacy_contractant_password}"
                    )
                )
            )

    def _replace_role_permissions(self, role, permissions):
        PermissionRole.objects.filter(id_role=role).delete()
        PermissionRole.objects.bulk_create(
            [PermissionRole(id_role=role, id_permission=permission) for permission in permissions],
            ignore_conflicts=True,
        )

    def _member_uuid(self, value):
        return uuid.UUID(int=int(value))

    def _replace_obsolete_roles(self):
        for old_name, new_name in OBSOLETE_ROLE_REPLACEMENTS.items():
            old_role = Role.objects.filter(nom_role=old_name).first()
            if not old_role:
                continue
            new_role, _ = Role.objects.get_or_create(nom_role=new_name)
            Utilisateur.objects.filter(id_role=old_role).update(id_role=new_role)
            PermissionRole.objects.filter(id_role=old_role).delete()
            old_role.delete()
