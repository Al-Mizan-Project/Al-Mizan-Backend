from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_service", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]