from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ServiceContractant",
            fields=[
                ("id_service", models.AutoField(primary_key=True, serialize=False)),
                ("id_tutelle", models.IntegerField(db_index=True)),
                ("categorie", models.CharField(max_length=255)),
                ("code_ordonnateur", models.CharField(max_length=100)),
            ],
            options={
                "db_table": "Services_Contractants",
            },
        ),
        migrations.CreateModel(
            name="CommissionExterne",
            fields=[
                ("id_comission_externe", models.AutoField(primary_key=True, serialize=False)),
                ("nom_comission", models.CharField(max_length=100)),
                ("niveau_competance", models.CharField(
                    choices=[
                        ("Communale", "Communale"),
                        ("de Wilaya", "de Wilaya"),
                        ("Sectorielle", "Sectorielle"),
                        ("Nationale", "Nationale"),
                    ],
                    max_length=20,
                )),
                ("seuils_competence_financiere", models.CharField(max_length=255)),
            ],
            options={
                "db_table": "Comission_Externe",
            },
        ),
        migrations.CreateModel(
            name="CommissionEvaluation",
            fields=[
                ("id_comission", models.AutoField(primary_key=True, serialize=False)),
                ("nom_comission", models.CharField(max_length=255)),
                ("categorie", models.CharField(max_length=255)),
                (
                    "id_service",
                    models.ForeignKey(
                        db_column="id_service",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commissions_evaluation",
                        to="contractant_service.servicecontractant",
                    ),
                ),
            ],
            options={
                "db_table": "Comission_evaluation",
            },
        ),
        migrations.CreateModel(
            name="CommissionInterne",
            fields=[
                ("id_comission_interne", models.AutoField(primary_key=True, serialize=False)),
                ("nom_comission", models.CharField(max_length=255)),
                ("type_comission", models.CharField(
                    choices=[("parmanante", "Parmanante"), ("adhoc", "Adhoc")],
                    max_length=20,
                )),
                (
                    "id_service",
                    models.ForeignKey(
                        db_column="id_service",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commissions_interne",
                        to="contractant_service.servicecontractant",
                    ),
                ),
            ],
            options={
                "db_table": "Comission_interne",
            },
        ),
        migrations.CreateModel(
            name="MembresCommissionEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_membre", models.IntegerField(db_index=True)),
                (
                    "id_comission",
                    models.ForeignKey(
                        db_column="id_comission",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membre_links",
                        to="contractant_service.commissionevaluation",
                    ),
                ),
            ],
            options={
                "db_table": "Membres_Commission_evaluation",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("id_membre", "id_comission"),
                        name="unique_membre_commission_eval",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="MembresCommissionInterne",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_membre", models.IntegerField(db_index=True)),
                (
                    "id_commision_interne",
                    models.ForeignKey(
                        db_column="id_commision_interne",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membre_links",
                        to="contractant_service.commissioninterne",
                    ),
                ),
            ],
            options={
                "db_table": "Membres_Commission_interne",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("id_membre", "id_commision_interne"),
                        name="unique_membre_commission_interne",
                    ),
                ],
            },
        ),
    ]
