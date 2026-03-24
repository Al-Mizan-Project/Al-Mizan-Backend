from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contrats_service", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="validation",
            old_name="id_organisation",
            new_name="id_utilisateur",
        ),
    ]
