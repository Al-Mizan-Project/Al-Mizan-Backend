from django.db import models
from auth_service.models import ServiceContractant, OperateurEconomique, Utilisateur
from tender_service.models import Soumission, Validation



class Contrat(models.Model):
    soumission = models.ForeignKey(
        Soumission,
        on_delete=models.CASCADE
    )

    service_contractant = models.ForeignKey(
        ServiceContractant,
        on_delete=models.CASCADE
    )

    numero_contrat = models.CharField(max_length=80)
    date_signature = models.DateTimeField()

    statut = models.CharField(max_length=30)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.numero_contrat


class Recours(models.Model):
    operateur_economique = models.ForeignKey(
        OperateurEconomique,
        on_delete=models.CASCADE
    )

    validation = models.ForeignKey(
        Validation,
        on_delete=models.CASCADE
    )

    motif = models.TextField()
    statut = models.CharField(max_length=30)

    date_depot = models.DateTimeField()

    decision = models.TextField()
    date_decision = models.DateTimeField(null=True, blank=True)
    traite_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)


