from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("soumissions_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="soumission",
            name="document_ids",
            field=models.JSONField(blank=True, default=list, help_text="Linked document IDs in Documents service"),
        ),
    ]
