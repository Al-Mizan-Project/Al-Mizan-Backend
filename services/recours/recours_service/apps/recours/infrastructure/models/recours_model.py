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

    id_recours = models.AutoField(primary_key=True)
    id_operateur_economique = models.IntegerField()
    id_validation = models.IntegerField()
    id_soumission = models.IntegerField(unique=True)

    motif = models.TextField()
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES)

    date_depot = models.DateTimeField()
    date_limite = models.DateTimeField()

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