from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels_service", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appeloffres",
            name="statut",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"),
                    ("publie", "Publié"),
                    ("depot_cloture", "Dépôt clôturé"),
                    ("plis_ouverts", "Plis ouverts"),
                    ("attribue", "Attribué"),
                    ("annule", "Annulé"),
                ],
                default="brouillon",
                max_length=30,
            ),
        ),
    ]
