from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels_service", "0002_alter_appeloffres_statut"),
    ]

    operations = [
        migrations.AddField(
            model_name="appeloffres",
            name="minimum_experience_years",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="minimum_revenue_da",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="participation_conditions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="qualification_category",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="required_docs_admin",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="required_docs_fin",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="required_docs_tech",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="wilaya",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
    ]
