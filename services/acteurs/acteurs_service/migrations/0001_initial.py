from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Membre",
            fields=[
                ("id_membre", models.AutoField(primary_key=True, serialize=False)),
                ("id_organisation", models.IntegerField(blank=True, null=True)),
                ("prenom", models.CharField(max_length=100)),
                ("nom", models.CharField(max_length=100)),
                ("telephone", models.CharField(blank=True, max_length=30)),
                ("fonction", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "membre",
            },
        ),
    ]
