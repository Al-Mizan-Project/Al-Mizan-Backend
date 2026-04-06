from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth_service", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="utilisateur",
            name="id_membre",
            field=models.IntegerField(db_index=True),
        ),
    ]
