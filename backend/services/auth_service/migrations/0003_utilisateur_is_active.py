from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth_service", "0002_alter_utilisateur_id_membre"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
