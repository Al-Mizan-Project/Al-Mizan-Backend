from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("auth_service", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UtilisateurPermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "id_permission",
                    models.ForeignKey(
                        db_column="id_permission",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_links",
                        to="auth_service.permission",
                    ),
                ),
                (
                    "id_utilisateur",
                    models.ForeignKey(
                        db_column="id_utilisateur",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permission_links",
                        to="auth_service.utilisateur",
                    ),
                ),
            ],
            options={
                "db_table": "Permission_utilisateur",
            },
        ),
        migrations.AddConstraint(
            model_name="utilisateurpermission",
            constraint=models.UniqueConstraint(
                fields=("id_utilisateur", "id_permission"),
                name="unique_user_permission",
            ),
        ),
    ]
