from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id_permission", models.AutoField(primary_key=True, serialize=False)),
                ("nom_permission", models.CharField(max_length=20, unique=True)),
            ],
            options={
                "db_table": "permission",
            },
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id_role", models.AutoField(primary_key=True, serialize=False)),
                ("nom_role", models.CharField(max_length=20, unique=True)),
            ],
            options={
                "db_table": "role",
            },
        ),
        migrations.CreateModel(
            name="Utilisateur",
            fields=[
                ("password", models.CharField(db_column="password_hash", max_length=255)),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("id_utilisateur", models.AutoField(primary_key=True, serialize=False)),
                ("id_membre", models.IntegerField()),
                ("email", models.EmailField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id_role",
                    models.ForeignKey(
                        db_column="id_role",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="utilisateurs",
                        to="auth_service.role",
                    ),
                ),
            ],
            options={
                "db_table": "utilisateurs",
            },
        ),
        migrations.CreateModel(
            name="PermissionRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "id_permission",
                    models.ForeignKey(
                        db_column="id_permission",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_links",
                        to="auth_service.permission",
                    ),
                ),
                (
                    "id_role",
                    models.ForeignKey(
                        db_column="id_role",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permission_links",
                        to="auth_service.role",
                    ),
                ),
            ],
            options={
                "db_table": "Permission_role",
                "constraints": [
                    models.UniqueConstraint(fields=("id_role", "id_permission"), name="unique_role_permission")
                ],
            },
        ),
    ]
