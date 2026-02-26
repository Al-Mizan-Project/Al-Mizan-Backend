from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("acteurs_service", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="membre",
            name="id_organisation",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="membre",
            name="nom",
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AlterField(
            model_name="membre",
            name="prenom",
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AddIndex(
            model_name="membre",
            index=models.Index(fields=["nom", "prenom"], name="membre_nom_prenom_idx"),
        ),
    ]
