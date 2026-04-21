from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appels_service", "0004_appeloffressuivi"),
    ]

    operations = [
        migrations.AddField(
            model_name="appeloffres",
            name="localisation",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="type_prestation",
            field=models.CharField(
                choices=[
                    ("travaux", "Travaux"),
                    ("fournitures", "Fournitures"),
                    ("services", "Services"),
                    ("etudes", "Etudes"),
                ],
                default="travaux",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="visibilite",
            field=models.CharField(
                choices=[("public", "Public"), ("prive", "Prive")],
                default="public",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="AchatSimple",
            fields=[
                ("id_achat_simple", models.AutoField(primary_key=True, serialize=False)),
                ("id_service_contractant", models.IntegerField(db_index=True)),
                ("reference", models.CharField(max_length=80, unique=True)),
                ("objet", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "type_prestation",
                    models.CharField(
                        choices=[
                            ("travaux", "Travaux"),
                            ("fournitures", "Fournitures"),
                            ("services", "Services"),
                            ("etudes", "Etudes"),
                        ],
                        default="fournitures",
                        max_length=20,
                    ),
                ),
                ("wilaya", models.CharField(blank=True, default="", max_length=80)),
                ("localisation", models.CharField(blank=True, default="", max_length=255)),
                (
                    "montant_estime",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
                ),
                ("id_operateur_economique", models.IntegerField(blank=True, db_index=True, null=True)),
                ("date_demande", models.DateTimeField(blank=True, null=True)),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("valide", "Valide"),
                            ("engage", "Engage"),
                            ("annule", "Annule"),
                        ],
                        default="brouillon",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "achats_simples",
            },
        ),
        migrations.CreateModel(
            name="AppelOffresOperateurInvite",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("id_operateur_economique", models.IntegerField(db_index=True)),
                (
                    "statut_invitation",
                    models.CharField(
                        choices=[
                            ("invite", "Invite"),
                            ("a_repondu", "A repondu"),
                            ("retire", "Retire"),
                        ],
                        default="invite",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id_appel_offres",
                    models.ForeignKey(
                        db_column="id_appel_offres",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="operateurs_invites",
                        to="appels_service.appeloffres",
                    ),
                ),
            ],
            options={
                "db_table": "appels_offres_operateurs_invites",
            },
        ),
        migrations.AddConstraint(
            model_name="appeloffresoperateurinvite",
            constraint=models.UniqueConstraint(
                fields=["id_appel_offres", "id_operateur_economique"],
                name="unique_appel_operateur_invite",
            ),
        ),
    ]
