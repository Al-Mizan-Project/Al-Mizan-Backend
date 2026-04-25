from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appels_service", "0003_appeloffres_real_contractant_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppelOffresSuivi",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_utilisateur", models.IntegerField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "id_appel_offres",
                    models.ForeignKey(
                        db_column="id_appel_offres",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="suivis",
                        to="appels_service.appeloffres",
                    ),
                ),
            ],
            options={
                "db_table": "appels_offres_suivis",
            },
        ),
        migrations.AddConstraint(
            model_name="appeloffressuivi",
            constraint=models.UniqueConstraint(
                fields=["id_appel_offres", "id_utilisateur"],
                name="unique_appel_suivi_user",
            ),
        ),
    ]
