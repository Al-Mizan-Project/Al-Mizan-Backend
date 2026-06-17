from django.db import models


class RecoursModel(models.Model):

    STATUT_CHOICES = [
        ("DEPOSE", "DEPOSE"),
        ("EN_INSTRUCTION", "EN_INSTRUCTION"),
        ("DECISION_PRISE", "DECISION_PRISE"),
        ("ACCEPTE", "ACCEPTE"),
        ("REJETE", "REJETE"),
        ("CLOTURE", "CLOTURE"),
    ]

    TYPE_RECOURS_CHOICES = [
        ("GRACIEUX", "Gracieux"),
        ("HIERARCHIQUE", "Hiérarchique"),
        ("CONTENTIEUX", "Contentieux"),
    ]

    id_recours = models.AutoField(primary_key=True)
    id_operateur_economique = models.IntegerField()
    id_validation = models.IntegerField(null=True, blank=True)
    id_soumission = models.IntegerField(unique=True)

    type_recours = models.CharField(
        max_length=20, choices=TYPE_RECOURS_CHOICES, null=True, blank=True
    )
    objet = models.CharField(max_length=255, blank=True, default="")
    explications = models.TextField(blank=True, default="")

    motif = models.TextField()
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES)

    date_depot = models.DateTimeField()
    date_limite = models.DateTimeField()
    date_fin_instruction = models.DateTimeField(null=True, blank=True)

    decision = models.TextField(null=True, blank=True)
    date_decision = models.DateTimeField(null=True, blank=True)

    traite_par = models.IntegerField(null=True, blank=True)

    version = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recours"

    def __str__(self):
        return f"Recours {self.id_recours} - {self.statut}"


class DocumentRecoursModel(models.Model):
    id_recours = models.ForeignKey(
        RecoursModel,
        on_delete=models.CASCADE,
        db_column="id_recours",
        related_name="document_links",
    )
    id_document = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "documents_recours"
        constraints = [
            models.UniqueConstraint(
                fields=["id_recours", "id_document"],
                name="documents_recours_unique_recours_document",
            ),
        ]