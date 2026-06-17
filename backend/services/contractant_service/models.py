from django.db import models


class ServiceContractant(models.Model):
    id_service = models.AutoField(primary_key=True)
    id_tutelle = models.IntegerField(db_index=True)
    categorie = models.CharField(max_length=255)
    code_ordonnateur = models.CharField(max_length=100)

    class Meta:
        db_table = "Services_Contractants"


class CommissionEvaluation(models.Model):
    id_comission = models.AutoField(primary_key=True)
    id_service = models.ForeignKey(
        ServiceContractant,
        on_delete=models.CASCADE,
        db_column="id_service",
        related_name="commissions_evaluation",
    )
    nom_comission = models.CharField(max_length=255)
    categorie = models.CharField(max_length=255)

    class Meta:
        db_table = "Comission_evaluation"


class CommissionInterne(models.Model):
    TYPE_CHOICES = [
        ("parmanante", "Parmanante"),
        ("adhoc", "Adhoc"),
    ]

    id_comission_interne = models.AutoField(primary_key=True)
    id_service = models.ForeignKey(
        ServiceContractant,
        on_delete=models.CASCADE,
        db_column="id_service",
        related_name="commissions_interne",
    )
    nom_comission = models.CharField(max_length=255)
    type_comission = models.CharField(max_length=20, choices=TYPE_CHOICES)

    class Meta:
        db_table = "Comission_interne"


class MembresCommissionEvaluation(models.Model):
    id_membre = models.IntegerField(db_index=True)
    id_comission = models.ForeignKey(
        CommissionEvaluation,
        on_delete=models.CASCADE,
        db_column="id_comission",
        related_name="membre_links",
    )

    class Meta:
        db_table = "Membres_Commission_evaluation"
        constraints = [
            models.UniqueConstraint(
                fields=["id_membre", "id_comission"],
                name="unique_membre_commission_eval",
            ),
        ]


class MembresCommissionInterne(models.Model):
    id_membre = models.IntegerField(db_index=True)
    id_commision_interne = models.ForeignKey(
        CommissionInterne,
        on_delete=models.CASCADE,
        db_column="id_commision_interne",
        related_name="membre_links",
    )

    class Meta:
        db_table = "Membres_Commission_interne"
        constraints = [
            models.UniqueConstraint(
                fields=["id_membre", "id_commision_interne"],
                name="unique_membre_commission_interne",
            ),
        ]


class CommissionExterne(models.Model):
    NIVEAU_CHOICES = [
        ("Communale", "Communale"),
        ("de Wilaya", "de Wilaya"),
        ("Sectorielle", "Sectorielle"),
        ("Nationale", "Nationale"),
    ]

    id_comission_externe = models.AutoField(primary_key=True)
    nom_comission = models.CharField(max_length=100)
    niveau_competance = models.CharField(max_length=20, choices=NIVEAU_CHOICES)
    seuils_competence_financiere = models.CharField(max_length=255)

class MembresCommissionExterne(models.Model):
    id_membre = models.IntegerField(db_index=True)
    id_comission_externe = models.ForeignKey(
        CommissionExterne,
        on_delete=models.CASCADE,
        db_column="id_comission_externe",
        related_name="membre_links",
    )

    class Meta:
        db_table = "Membres_Commission_Externe"
        constraints = [
            models.UniqueConstraint(
                fields=["id_membre", "id_comission_externe"],
                name="unique_membre_commission_externe",
            ),
        ]
