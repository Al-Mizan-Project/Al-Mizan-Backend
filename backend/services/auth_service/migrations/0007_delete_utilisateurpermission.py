from django.db import migrations


def move_obsolete_roles(apps, schema_editor):
    Role = apps.get_model("auth_service", "Role")
    PermissionRole = apps.get_model("auth_service", "PermissionRole")
    Utilisateur = apps.get_model("auth_service", "Utilisateur")
    replacements = {
        "VALIDATEUR_INTERNE": "VALIDATEUR_INTERNE_MARCHE",
        "VALIDATEUR_EXTERNE": "VALIDATEUR_EXTERNE_MARCHE",
    }
    for old_name, new_name in replacements.items():
        old_role = Role.objects.filter(nom_role=old_name).first()
        if not old_role:
            continue
        new_role = Role.objects.filter(nom_role=new_name).first()
        if new_role:
            Utilisateur.objects.filter(id_role=old_role).update(id_role=new_role)
            PermissionRole.objects.filter(id_role=old_role).delete()
            old_role.delete()
        else:
            old_role.nom_role = new_name
            old_role.save(update_fields=["nom_role"])


class Migration(migrations.Migration):

    dependencies = [
        ("auth_service", "0006_utilisateur_must_change_password"),
    ]

    operations = [
        migrations.RunPython(move_obsolete_roles, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="UtilisateurPermission",
        ),
    ]
