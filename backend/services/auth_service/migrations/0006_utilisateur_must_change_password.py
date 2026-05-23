from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_service", "0005_alter_permissionrole_id_alter_utilisateur_id_membre"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
    ]
