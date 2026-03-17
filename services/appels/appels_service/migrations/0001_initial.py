from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AppelOffres",
            fields=[
                ("id_appel_offres", models.AutoField(primary_key=True, serialize=False)),
                ("id_service_contractant", models.IntegerField(db_index=True)),
                ("reference", models.CharField(max_length=80, unique=True)),
                ("titre", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("type_procedure", models.CharField(max_length=50)),
                (
                    "montant_estime",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
                ),
                ("date_publication", models.DateTimeField(blank=True, null=True)),
                ("date_limite_soumission", models.DateTimeField(blank=True, null=True)),
                ("date_ouverture_plis", models.DateTimeField(blank=True, null=True)),
                ("poids_technique", models.IntegerField(default=50)),
                ("poids_financier", models.IntegerField(default=50)),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("publie", "Publié"),
                            ("depot_cloture", "Dépôt clôturé"),
                            ("plis_ouverts", "Plis ouverts"),
                            ("annule", "Annulé"),
                        ],
                        default="brouillon",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "appels_offres",
            },
        ),
        migrations.CreateModel(
            name="DocumentsAppel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("id_document", models.IntegerField(db_index=True)),
                (
                    "id_appel_offres",
                    models.ForeignKey(
                        db_column="id_appel_offres",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_links",
                        to="appels_service.appeloffres",
                    ),
                ),
            ],
            options={
                "db_table": "documents_appel",
            },
        ),
        migrations.AddConstraint(
            model_name="documentsappel",
            constraint=models.UniqueConstraint(
                fields=["id_document", "id_appel_offres"],
                name="unique_document_appel",
            ),
        ),
    ]
