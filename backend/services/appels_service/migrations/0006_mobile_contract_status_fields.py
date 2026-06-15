from django.db import migrations, models


def forwards(apps, schema_editor):
    AppelOffres = apps.get_model("appels_service", "AppelOffres")

    execution_map = {
        "brouillon": ("non_valide", "brouillon"),
        "publie": ("valide", "publie"),
        "depot_cloture": ("valide", "depot_cloture"),
        "plis_ouverts": ("valide", "plis_ouverts"),
        "attribue": ("ferme", "plis_ouverts"),
        "attribuee": ("ferme", "plis_ouverts"),
        "annule": ("refuse", "annule"),
    }

    for appel in AppelOffres.objects.all().iterator():
        old_statut = (appel.statut or "").strip().lower()
        statut, etat_execution = execution_map.get(old_statut, ("non_valide", "brouillon"))

        raw_type = (appel.type_procedure or "").strip().lower()
        if raw_type in {"publique", "public"} or "ouvert" in raw_type:
            type_procedure = "publique"
        elif raw_type in {"restreint", "restreinte"} or "restreint" in raw_type:
            type_procedure = "restreint"
        elif raw_type in {"gre_a_gre", "gre a gre", "gré à gré"}:
            type_procedure = "gre_a_gre"
        elif "consult" in raw_type:
            type_procedure = "consultation"
        else:
            type_procedure = "publique"

        appel.statut = statut
        appel.etat_execution = etat_execution
        appel.type_procedure = type_procedure
        appel.save(update_fields=["statut", "etat_execution", "type_procedure"])


def backwards(apps, schema_editor):
    AppelOffres = apps.get_model("appels_service", "AppelOffres")
    for appel in AppelOffres.objects.all().iterator():
        appel.statut = appel.etat_execution or "brouillon"
        appel.save(update_fields=["statut"])


class Migration(migrations.Migration):

    dependencies = [
        ("appels_service", "0005_appeloffres_enrichment_and_achats_simples"),
    ]

    operations = [
        migrations.AddField(
            model_name="appeloffres",
            name="commission_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="etat_execution",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"),
                    ("publie", "Publie"),
                    ("depot_cloture", "Depot cloture"),
                    ("plis_ouverts", "Plis ouverts"),
                    ("annule", "Annule"),
                ],
                default="brouillon",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="validated_by",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appeloffres",
            name="validation_level",
            field=models.CharField(
                choices=[
                    ("aucun", "Aucun"),
                    ("interne", "Interne"),
                    ("externe_wilaya", "Externe wilaya"),
                    ("externe_secteur", "Externe secteur"),
                    ("externe_nationale", "Externe nationale"),
                ],
                default="aucun",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="appeloffres",
            name="poids_financier",
            field=models.IntegerField(blank=True, default=50, null=True),
        ),
        migrations.AlterField(
            model_name="appeloffres",
            name="poids_technique",
            field=models.IntegerField(blank=True, default=50, null=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="appeloffres",
            name="statut",
            field=models.CharField(
                choices=[
                    ("non_valide", "Non valide"),
                    ("valide", "Valide"),
                    ("refuse", "Refuse"),
                    ("ferme", "Ferme"),
                ],
                default="non_valide",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="appeloffres",
            name="type_procedure",
            field=models.CharField(
                choices=[
                    ("publique", "Publique"),
                    ("restreint", "Restreint"),
                    ("gre_a_gre", "Gre a gre"),
                    ("consultation", "Consultation"),
                ],
                max_length=50,
            ),
        ),
    ]
