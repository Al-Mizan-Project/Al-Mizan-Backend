from django.db import models

class Document(models.Model):
    id_document = models.AutoField(primary_key=True)
    related_type = models.CharField(max_length=50) # ex: appel_offre, soumission, contrat
    id_operateur_economique = models.IntegerField(null=True, blank=True, db_index=True)  # Owner operator
    nom = models.CharField(max_length=255) # Nom original complet
    type_document = models.CharField(max_length=50) # Extension/MimeType
    storage_url = models.CharField(max_length=500, unique=True) # Chemin d'accès unique dans MinIO (UUID.ext)
    hash_sha256 = models.CharField(max_length=64) # Empreinte d'intégrité
    taille_fichier = models.BigIntegerField(default=0) # Taille du fichier en octets
    is_encrypted = models.BooleanField(default=False)
    
    # AI Processing fields
    STATUT_CHOICES = [
        ('PENDING', 'Pending'),
        ('VALID', 'Valid'),
        ('ANOMALY', 'Anomaly'),
    ]
    ia_verif_statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default='PENDING')
    ia_verif_details = models.TextField(blank=True, null=True) # JSON ou log
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    visible_after = models.DateTimeField(null=True, blank=True) # Date à partir de laquelle le document est visible

    class Meta:
        db_table = "documents"

    def __str__(self):
        return f"{self.nom} ({self.related_type})"
