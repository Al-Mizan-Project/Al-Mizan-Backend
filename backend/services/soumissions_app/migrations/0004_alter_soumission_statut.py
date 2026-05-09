from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('soumissions_app', '0003_remove_evaluation_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='soumission',
            name='statut',
            field=models.CharField(
                choices=[
                    ('SOUMIS', 'Soumis'),
                    ('EN_OUVERTURE', 'En Ouverture'),
                    ('EN_EVALUATION', 'En Évaluation'),
                    ('EVALU_TERMINEE', 'Évaluation Terminée'),
                    ('ATTRIBUE', 'Attribué'),
                    ('NON_RETENU', 'Non Retenu'),
                    ('INFRUCTUEUX', 'Infructueux'),
                    ('RETRAITE', 'Retraitée'),
                ],
                default='SOUMIS',
                max_length=50,
            ),
        ),
    ]
