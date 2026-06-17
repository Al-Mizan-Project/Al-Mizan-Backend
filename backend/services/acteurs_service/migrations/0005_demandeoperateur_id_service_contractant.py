from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("acteurs_service", "0004_remove_tutelle_organisation_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="demandeoperateur",
            name="id_service_contractant",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
    ]
