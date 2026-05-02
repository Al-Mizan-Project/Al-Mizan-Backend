from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents_service", "0003_document_visible_after"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="id_operateur_economique",
            field=models.IntegerField(null=True, blank=True, db_index=True),
        ),
    ]
