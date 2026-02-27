from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Validation",
            fields=[
                ("id_validation", models.AutoField(primary_key=True, serialize=False)),
                ("id_organisation", models.IntegerField()),
                ("id_soumission", models.IntegerField()),
                ("type", models.CharField(
                    choices=[("interne", "Interne"), ("externe", "Externe"), ("tutelle", "Tutelle")],
                    max_length=20,
                )),
                ("is_validated", models.BooleanField(default=False)),
                ("commentaire", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "validation",
            },
        ),
        migrations.CreateModel(
            name="Contrat",
            fields=[
                ("id_contrat", models.AutoField(primary_key=True, serialize=False)),
                ("id_soumission", models.IntegerField()),
                ("id_service_contractants", models.IntegerField()),
                ("numero_contrat", models.CharField(max_length=80, unique=True)),
                ("date_signature", models.DateTimeField(blank=True, null=True)),
                ("statut", models.CharField(default="brouillon", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "contrats",
            },
        ),
        migrations.CreateModel(
            name="DocumentContrat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_document", models.IntegerField()),
                ("id_contrat", models.ForeignKey(
                    db_column="id_contrat",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="document_links",
                    to="contrats_service.contrat",
                )),
            ],
            options={
                "db_table": "documents_contrats",
            },
        ),
        migrations.AddConstraint(
            model_name="documentcontrat",
            constraint=models.UniqueConstraint(
                fields=("id_contrat", "id_document"),
                name="unique_contrat_document",
            ),
        ),
    ]
