from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("acteurs_service", "0002_membre_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="OperateurEconomique",
            fields=[
                ("id_operateur_economique", models.AutoField(primary_key=True, serialize=False)),
                ("nif", models.CharField(max_length=100, unique=True)),
                ("registre_commerce_num", models.CharField(blank=True, max_length=100)),
                ("casnos_vrt", models.CharField(blank=True, max_length=100)),
                ("cnas_vrt", models.CharField(blank=True, max_length=100)),
                ("rib_bancaire", models.CharField(blank=True, max_length=100)),
            ],
            options={
                "db_table": "Operateurs_Economiques",
            },
        ),
        migrations.CreateModel(
            name="Organisation",
            fields=[
                ("id_organisation", models.AutoField(primary_key=True, serialize=False)),
                ("nom_officiel", models.CharField(db_index=True, max_length=20)),
                ("adresse_siege", models.CharField(blank=True, max_length=100)),
                ("email_contact", models.EmailField(blank=True, max_length=100)),
                ("type_entite", models.CharField(db_index=True, max_length=30)),
            ],
            options={
                "db_table": "Organisation",
            },
        ),
        migrations.CreateModel(
            name="Tutelle",
            fields=[
                ("id_tutelle", models.AutoField(primary_key=True, serialize=False)),
                ("nom_tutelle", models.CharField(max_length=255, unique=True)),
                ("identite_autorite", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "db_table": "Tutelle",
            },
        ),
        migrations.AddIndex(
            model_name="organisation",
            index=models.Index(fields=["type_entite", "nom_officiel"], name="organisation_type_nom_idx"),
        ),
    ]
