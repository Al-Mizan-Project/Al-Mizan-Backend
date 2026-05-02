import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id_role", models.AutoField(primary_key=True, serialize=False)),
                ("nom_role", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "db_table": "role",
            },
        ),
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id_permission", models.AutoField(primary_key=True, serialize=False)),
                ("nom_permission", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "db_table": "permission",
            },
        ),
        migrations.CreateModel(
            name="PermissionRole",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_role", models.ForeignKey(db_column="id_role", on_delete=django.db.models.deletion.CASCADE, related_name="permission_links", to="auth_service.role")),
                ("id_permission", models.ForeignKey(db_column="id_permission", on_delete=django.db.models.deletion.CASCADE, related_name="role_links", to="auth_service.permission")),
            ],
            options={
                "db_table": "Permission_role",
            },
        ),
        migrations.AddConstraint(
            model_name="permissionrole",
            constraint=models.UniqueConstraint(fields=["id_role", "id_permission"], name="unique_role_permission"),
        ),
        migrations.CreateModel(
            name="Utilisateur",
            fields=[
                ("id_utilisateur", models.AutoField(primary_key=True, serialize=False)),
                ("id_membre", models.UUIDField(db_index=True)),
                ("email", models.EmailField(max_length=255, unique=True)),
                ("password", models.CharField(db_column="password_hash", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("id_role", models.ForeignKey(db_column="id_role", on_delete=django.db.models.deletion.PROTECT, related_name="utilisateurs", to="auth_service.role")),
            ],
            options={
                "db_table": "utilisateurs",
            },
        ),
    ]