from django.db import models


class RecoursModel(models.Model):
    id_recours = models.AutoField(primary_key=True)
    id_operateur_economique = models.IntegerField()
    id_validation = models.IntegerField()
    id_soumission = models.IntegerField()
    motif = models.TextField()
    statut = models.CharField(max_length=50)
    date_depot = models.DateTimeField()
    date_limite = models.DateTimeField()
    decision = models.TextField(null=True)
    date_decision = models.DateTimeField(null=True)
    traite_par = models.IntegerField(null=True)
    version = models.IntegerField()

    def save(self, *args, **kwargs): ...