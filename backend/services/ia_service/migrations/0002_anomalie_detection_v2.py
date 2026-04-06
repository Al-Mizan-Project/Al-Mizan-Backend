"""
Migration for enhanced anomaly detection model.

Adds:
- Nullable id_soumission (saucissonnage anomalies don't target a specific soumission)
- JSONFields for soumissions_impliquees and appels_impliques
- Reviewer tracking fields (examiné_par, commentaire_examen, date_examen)
- Database indexes for common query patterns
- TextChoices for type_anomalie, niveau_severite, statut_examen
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ia_service", "0001_initial"),
    ]

    operations = [
        # 1. Make id_soumission nullable (saucissonnage anomalies don't have one)
        migrations.AlterField(
            model_name="detectionanomalieia",
            name="id_soumission",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        # 2. Add db_index to id_appel_offre
        migrations.AlterField(
            model_name="detectionanomalieia",
            name="id_appel_offre",
            field=models.IntegerField(db_index=True),
        ),
        # 3. Add choices to type_anomalie
        migrations.AlterField(
            model_name="detectionanomalieia",
            name="type_anomalie",
            field=models.CharField(
                choices=[
                    ("SIMILARITE_PRIX", "Similarité de prix"),
                    ("SIMILARITE_DOCUMENTAIRE", "Similarité documentaire"),
                    ("COLLUSION_CLUSTER_PRIX", "Cluster de prix collusoire"),
                    ("ROTATION_SOUMISSIONNAIRES", "Rotation de soumissionnaires"),
                    ("OFFRES_COMPLEMENTAIRES", "Offres de couverture"),
                    ("DISPERSION_ANORMALE", "Dispersion anormale des prix"),
                    ("PRIX_ANORMALEMENT_BAS", "Prix anormalement bas"),
                    ("PRIX_ANORMALEMENT_ELEVE", "Prix anormalement élevé"),
                    ("BIAIS_NOMBRES_RONDS", "Biais de nombres ronds"),
                    ("SAUCISSONNAGE_PROXIMITE_SEUIL", "Proximité de seuil réglementaire"),
                    ("SAUCISSONNAGE_TEMPOREL", "Clustering temporel suspect"),
                    ("SAUCISSONNAGE_CUMUL_SEUIL", "Dépassement cumulé de seuil"),
                    ("SAUCISSONNAGE_MEME_FOURNISSEUR", "Même fournisseur multi-marchés"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
        # 4. Add choices to niveau_severite
        migrations.AlterField(
            model_name="detectionanomalieia",
            name="niveau_severite",
            field=models.CharField(
                choices=[
                    ("CRITIQUE", "Critique"),
                    ("ELEVEE", "Élevée"),
                    ("MOYEN", "Moyen"),
                    ("FAIBLE", "Faible"),
                ],
                max_length=20,
            ),
        ),
        # 5. Add choices to statut_examen
        migrations.AlterField(
            model_name="detectionanomalieia",
            name="statut_examen",
            field=models.CharField(
                choices=[
                    ("A_REVOIR", "À revoir"),
                    ("EN_COURS", "En cours d'examen"),
                    ("CONFIRMEE", "Confirmée"),
                    ("REJETEE", "Rejetée (faux positif)"),
                    ("SIGNALEE", "Signalée à la tutelle"),
                ],
                default="A_REVOIR",
                max_length=30,
            ),
        ),
        # 6. Add JSONFields for implicated entities
        migrations.AddField(
            model_name="detectionanomalieia",
            name="soumissions_impliquees",
            field=models.JSONField(
                blank=True,
                help_text="List of soumission IDs involved in this anomaly pattern",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="detectionanomalieia",
            name="appels_impliques",
            field=models.JSONField(
                blank=True,
                help_text="List of appel d'offre IDs involved (for saucissonnage)",
                null=True,
            ),
        ),
        # 7. Add reviewer tracking fields
        migrations.AddField(
            model_name="detectionanomalieia",
            name="examiné_par",
            field=models.IntegerField(
                blank=True,
                help_text="User ID who reviewed this anomaly",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="detectionanomalieia",
            name="commentaire_examen",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Reviewer's comment on the anomaly",
            ),
        ),
        migrations.AddField(
            model_name="detectionanomalieia",
            name="date_examen",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # 8. Add composite indexes
        migrations.AddIndex(
            model_name="detectionanomalieia",
            index=models.Index(
                fields=["id_appel_offre", "type_anomalie"],
                name="idx_appel_type",
            ),
        ),
        migrations.AddIndex(
            model_name="detectionanomalieia",
            index=models.Index(
                fields=["statut_examen", "niveau_severite"],
                name="idx_statut_severite",
            ),
        ),
    ]
