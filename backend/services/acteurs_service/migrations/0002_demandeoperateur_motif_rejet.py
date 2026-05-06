from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("acteurs_service", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="demandeoperateur",
            name="motif_rejet",
            field=models.TextField(blank=True, default=""),
        ),
    ]
