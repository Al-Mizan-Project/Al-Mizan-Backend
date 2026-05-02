import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Organisation",
            fields=[
                ("id_organisation", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom_officiel", models.CharField(default="Organisation Anonyme", max_length=255)),
                ("adresse_siege", models.CharField(blank=True, default="", max_length=100, null=True)),
                ("email_contact", models.CharField(blank=True, default="", max_length=100, null=True)),
                ("type_entite", models.CharField(
                    choices=[
                        ("OPERATEUR_ECONOMIQUE", "Opérateur Économique"),
                        ("SERVICE_CONTRACTANT", "Service Contractant"),
                        ("COMMISSION_EXTERNE", "Commission Externe"),
                        ("TUTELLE", "Tutelle"),
                    ],
                    default="OPERATEUR_ECONOMIQUE",
                    max_length=30,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "organisation"},
        ),
        migrations.CreateModel(
            name="DemandeOperateur",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom_organisation", models.CharField(default="Non renseigné", max_length=255)),
                ("email_contact", models.EmailField(default="contact@defaut.dz")),
                ("telephone", models.CharField(default="0000000000", max_length=50)),
                ("nif", models.CharField(default="000000000000000", max_length=50)),
                ("num_registre_commerce", models.CharField(default="RC-DEFAULT", max_length=100)),
                ("statut", models.CharField(
                    choices=[
                        ("EN_ATTENTE", "En attente"),
                        ("APPROUVE", "Approuvé"),
                        ("REJETE", "Rejeté"),
                    ],
                    default="EN_ATTENTE",
                    max_length=20,
                )),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("mis_a_jour_le", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="DemandeDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("demande", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="acteurs_service.demandeoperateur")),
                ("document_id", models.IntegerField(default=0, help_text="ID du fichier dans le service Document")),
                ("type_document", models.CharField(
                    choices=[
                        ("REGISTRE_COMMERCE", "Registre de commerce"),
                        ("NIF", "Carte fiscale (NIF)"),
                        ("CNAS_CASNOS", "Attestation CNAS / CASNOS"),
                        ("NON_FAILLITE", "Certificat de non-faillite"),
                    ],
                    default="REGISTRE_COMMERCE",
                    max_length=30,
                )),
            ],
        ),
        migrations.CreateModel(
            name="OperateurEconomique",
            fields=[
                ("organisation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="operateur_economique", serialize=False, to="acteurs_service.organisation")),
                ("nif", models.CharField(default="000000000000000", max_length=50)),
                ("num_registre_commerce", models.CharField(default="RC-DEFAULT", max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="ServiceContractant",
            fields=[
                ("organisation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="service_contractant", serialize=False, to="acteurs_service.organisation")),
                ("code_service", models.CharField(default="SC-000", max_length=50)),
                ("secteur_activite", models.CharField(default="Non défini", max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="CommissionExterne",
            fields=[
                ("organisation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="commission_externe", serialize=False, to="acteurs_service.organisation")),
                ("numero_agrement", models.CharField(default="AGR-000", max_length=50)),
                ("specialite", models.CharField(default="Générale", max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Tutelle",
            fields=[
                ("organisation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="tutelle", serialize=False, to="acteurs_service.organisation")),
                ("ministere_attache", models.CharField(default="Ministère non assigné", max_length=150)),
            ],
        ),
        migrations.CreateModel(
            name="Membre",
            fields=[
                ("id_membre", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("organisation", models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="membres", to="acteurs_service.organisation")),
                ("nom", models.CharField(default="Anonyme", max_length=100)),
                ("prenom", models.CharField(default="Anonyme", max_length=100)),
                ("telephone", models.CharField(blank=True, default="", max_length=30, null=True)),
                ("fonction", models.CharField(blank=True, default="Employé", max_length=50, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "membre"},
        ),
    ]