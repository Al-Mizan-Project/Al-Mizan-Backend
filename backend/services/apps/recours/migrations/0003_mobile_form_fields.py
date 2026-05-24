from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recours", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recoursmodel",
            name="id_validation",
            field=models.IntegerField(
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="recoursmodel",
            name="type_recours",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("GRACIEUX", "Gracieux"),
                    ("HIERARCHIQUE", "Hiérarchique"),
                    ("CONTENTIEUX", "Contentieux"),
                ],
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="recoursmodel",
            name="objet",
            field=models.CharField(
                max_length=255,
                blank=True,
                default="",
            ),
        ),
        migrations.AddField(
            model_name="recoursmodel",
            name="explications",
            field=models.TextField(
                blank=True,
                default="",
            ),
        ),
    ]