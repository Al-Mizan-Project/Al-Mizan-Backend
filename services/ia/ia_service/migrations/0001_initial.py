from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DetectionAnomalieIA",
            fields=[
                ("id_detection_anomalie_ia", models.AutoField(primary_key=True, serialize=False)),
                ("id_appel_offre", models.IntegerField()),
                ("id_soumission", models.IntegerField()),
                ("type_anomalie", models.CharField(max_length=50)),
                ("niveau_severite", models.CharField(max_length=20)),
                ("score_confiance", models.DecimalField(decimal_places=2, max_digits=5)),
                ("details", models.TextField(blank=True, default="")),
                ("statut_examen", models.CharField(default="A_REVOIR", max_length=30)),
                ("date_detection", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "detection_anomalie_ia",
                "ordering": ["-date_detection", "-id_detection_anomalie_ia"],
            },
        ),
    ]