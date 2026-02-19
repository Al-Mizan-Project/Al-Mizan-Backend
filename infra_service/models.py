from django.db import models
from auth_service.models import Utilisateur
from tender_service.models import Soumission, AppelOffres
from contract_service.models import Contrat, Recours


class Document(models.Model):
    related_type = models.CharField(max_length=30)

    nom = models.CharField(max_length=255)
    type_document = models.CharField(max_length=50)

    storage_url = models.CharField(max_length=500)

    hash_sha256 = models.CharField(max_length=64)
    is_encrypted = models.BooleanField()

    ia_verif_statut = models.CharField(max_length=30)
    ia_verif_details = models.TextField()

    uploaded_at = models.DateTimeField()


class Notification(models.Model):
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE
    )

    type_notification = models.CharField(max_length=50)
    titre = models.CharField(max_length=255)
    message = models.TextField()

    priorite = models.CharField(max_length=20)
    categorie = models.CharField(max_length=50)

    entite_liee_type = models.CharField(max_length=30)
    entite_liee_id = models.IntegerField()

    statut = models.CharField(max_length=30)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)


class JournalAudit(models.Model):
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE
    )

    action = models.CharField(max_length=100)

    entite_type = models.CharField(max_length=30)
    entite_id = models.IntegerField()

    horodatage = models.DateTimeField()

    adresse_ip = models.CharField(max_length=45)

    hash_log_precedent = models.CharField(max_length=64)
    hash_log_actuel = models.CharField(max_length=64)

    details_action = models.TextField()



class DocumentSoumission(models.Model):
    soumission = models.ForeignKey(Soumission, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)


class DocumentAppel(models.Model):
    appel_offre = models.ForeignKey(AppelOffres, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)


class DocumentContrat(models.Model):
    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)


class DocumentRecours(models.Model):
    recours = models.ForeignKey(Recours, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)


