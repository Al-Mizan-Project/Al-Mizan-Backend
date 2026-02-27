from django.db import models


class Validation(models.Model):
    id_validation = models.AutoField(primary_key=True)
    id_organisation = models.IntegerField()
    id_soumission = models.IntegerField()
    type = models.CharField(
        max_length=20,
        choices=[
            ("interne", "Interne"),
            ("externe", "Externe"),
            ("tutelle", "Tutelle"),
        ],
    )
    is_validated = models.BooleanField(default=False)
    commentaire = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "validation"


class Contrat(models.Model):
    id_contrat = models.AutoField(primary_key=True)
    id_soumission = models.IntegerField()
    id_service_contractants = models.IntegerField()
    numero_contrat = models.CharField(max_length=80, unique=True)
    date_signature = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=30, default="brouillon")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contrats"


class DocumentContrat(models.Model):
    id_contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        db_column="id_contrat",
        related_name="document_links",
    )
    id_document = models.IntegerField()

    class Meta:
        db_table = "documents_contrats"
        constraints = [
            models.UniqueConstraint(
                fields=["id_contrat", "id_document"],
                name="unique_contrat_document",
            ),
        ]
