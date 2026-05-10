from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_service", "0004_utilisateurpermission"),
    ]

    operations = [
        migrations.AlterField(
            model_name="permissionrole",
            name="id",
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
        ),
        migrations.AlterField(
            model_name="utilisateur",
            name="id_membre",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
