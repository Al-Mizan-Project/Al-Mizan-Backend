from django.db import models
from auth_service.models import (
    ServiceContractant,
    Organisation,
    CommissionEvaluation,
)

class AppelOffres(models.Model):
    service_contractant = models.ForeignKey(
        ServiceContractant,
        on_delete=models.CASCADE
    )

    reference = models.CharField(max_length=80)
    titre = models.CharField(max_length=255)
    description = models.TextField()

    type_procedure = models.CharField(max_length=50)
    montant_estime = models.DecimalField(max_digits=15, decimal_places=2)

    date_publication = models.DateTimeField()
    date_limite_soumission = models.DateTimeField()
    date_ouverture_plis = models.DateTimeField()

    poids_technique = models.IntegerField()
    poids_financier = models.IntegerField()

    statut = models.CharField(max_length=30)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.reference

class Soumission(models.Model):
    appel_offre = models.ForeignKey(
        AppelOffres,
        on_delete=models.CASCADE
    )

    date_soumission = models.DateTimeField()
    montant_financier = models.DecimalField(max_digits=15, decimal_places=2)

    offre_financiere_chiffree_url = models.CharField(max_length=500)
    cle_dechiffrement_hash = models.CharField(max_length=255)

    statut = models.CharField(max_length=30)
    conformite_statut = models.CharField(max_length=30)
    conformite_rapport = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Validation(models.Model):
    TYPE_CHOICES = [
        ('interne', 'Interne'),
        ('externe', 'Externe'),
        ('tutelle', 'Tutelle'),
    ]

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE
    )

    soumission = models.ForeignKey(
        Soumission,
        on_delete=models.CASCADE
    )

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    is_validated = models.BooleanField()
    commentaire = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Evaluation(models.Model):
    TYPE_CHOICES = [
        ('administrative', 'Administrative'),
        ('technique', 'Technique'),
        ('financiere', 'Financiere'),
    ]

    commission = models.ForeignKey(
        CommissionEvaluation,
        on_delete=models.CASCADE
    )

    soumission = models.ForeignKey(
        Soumission,
        on_delete=models.CASCADE
    )

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    note = models.IntegerField()
    commentaire = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class DetectionAnomalieIA(models.Model):
    appel_offre = models.ForeignKey(
        AppelOffres,
        on_delete=models.CASCADE
    )

    soumission = models.ForeignKey(
        Soumission,
        on_delete=models.CASCADE
    )

    type_anomalie = models.CharField(max_length=50)
    niveau_severite = models.CharField(max_length=20)

    score_confiance = models.DecimalField(max_digits=5, decimal_places=2)

    details = models.TextField()
    statut_examen = models.CharField(max_length=30)

    date_detection = models.DateTimeField()

