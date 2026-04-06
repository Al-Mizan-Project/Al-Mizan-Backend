from django.db import models

class ComissionEvaluation(models.Model):
    id_comission = models.AutoField(primary_key=True)
    id_service = models.IntegerField()
    nom_comission = models.CharField(max_length=255)
    categorie = models.CharField(max_length=255)

    class Meta:
        db_table = "comission_evaluation"


class MembresCommissionEvaluation(models.Model):
    id_comission = models.ForeignKey(
        ComissionEvaluation,
        on_delete=models.CASCADE,
        db_column="id_comission",
        related_name="membres"
    )
    id_utilisateur = models.IntegerField()

    class Meta:
        db_table = "membres_commission_evaluation"
        constraints = [
            models.UniqueConstraint(
                fields=["id_comission", "id_utilisateur"],
                name="unique_membre_commission"
            )
        ]


class Evaluation(models.Model):
    EVALUATION_TYPES = [
        ("administrative", "Administrative"),
        ("technique", "Technique"),
        ("financière", "Financière")
    ]

    id_evalution = models.AutoField(primary_key=True)
    id_comission = models.ForeignKey(
        ComissionEvaluation,
        on_delete=models.CASCADE,
        db_column="id_comission",
        related_name="evaluations"
    )
    id_soumission = models.IntegerField()
    id_utilisateur = models.IntegerField()
    type = models.CharField(max_length=20, choices=EVALUATION_TYPES)
    note = models.IntegerField()
    commentaire = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "evaluation"
        constraints = [
            models.UniqueConstraint(
                fields=["id_comission", "id_soumission", "id_utilisateur", "type"],
                name="unique_evaluation_par_membre"
            )
        ]
