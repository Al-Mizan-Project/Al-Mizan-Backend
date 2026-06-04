from django.db import models

class SoumissionStatut(models.TextChoices):
    SOUMIS = 'SOUMIS', 'Soumis'
    EN_OUVERTURE = 'EN_OUVERTURE', 'En Ouverture'
    EN_EVALUATION = 'EN_EVALUATION', 'En Évaluation'
    EVALU_TERMINEE = 'EVALU_TERMINEE', 'Évaluation Terminée'
    ATTRIBUE = 'ATTRIBUE', 'Attribué'
    NON_RETENU = 'NON_RETENU', 'Non Retenu'
    INFRUCTUEUX = 'INFRUCTUEUX', 'Infructueux'
    RETRAITE = 'RETRAITE', 'Retraitée'

class Soumission(models.Model):
    id_soumission = models.AutoField(primary_key=True)
    id_appel_offre = models.IntegerField(help_text="Reference to the Appel d'Offre in the Appels Service")
    id_soumissionnaire = models.IntegerField(help_text="Reference to the Entreprise/User in Auth Service")
    
    # Financial Offer Encryption
    offre_financiere_chiffree_url = models.URLField(max_length=500, help_text="MinIO URL of the encrypted PDF")
    cle_dechiffrement_hash = models.TextField(help_text="AES Key encrypted with Appel d'Offre public RSA key")
    document_ids = models.JSONField(default=list, blank=True, help_text="Linked document IDs in Documents service")
    
    statut = models.CharField(
        max_length=50, 
        choices=SoumissionStatut.choices, 
        default=SoumissionStatut.SOUMIS
    )
    
    # Decrypted later
    montant_financier = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Filled ONLY after official opening of bids"
    )
    
    date_soumission = models.DateTimeField(auto_now_add=True)
    
    # AI Analysis Fields
    conformite_statut = models.CharField(max_length=100, null=True, blank=True)
    conformite_rapport = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'soumissions'
        # One soumissionnaire can submit only one active bid per appel_offre (mostly)
        # But they might retry/replace it before date_limite_soumission. We'll leave it without strict unique constraint for now, 
        # handling uniqueness in the business logic if necessary.

    def __str__(self):
        return f"Soumission #{self.id_soumission} - AO #{self.id_appel_offre}"


class SoumissionEvaluateur(models.Model):
    """Assigns evaluators to a soumission."""
    TYPE_CHOICES = [
        ('technique', 'Technique / Financière'),
        ('administrative', 'Administrative'),
    ]
    id = models.AutoField(primary_key=True)
    soumission = models.ForeignKey(Soumission, on_delete=models.CASCADE, related_name='evaluateurs_assignes')
    evaluateur = models.ForeignKey('auth_service.Utilisateur', on_delete=models.CASCADE, related_name='soumissions_a_evaluer')
    type_evaluation = models.CharField(max_length=20, choices=TYPE_CHOICES)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'soumission_evaluateur'
        unique_together = [['soumission', 'evaluateur', 'type_evaluation']]

    def __str__(self):
        return f"Soumission {self.soumission.id_soumission} → Evaluateur {self.evaluateur.id_utilisateur} ({self.type_evaluation})"
        
class Attribution(models.Model):
    VALIDATION_LEVEL_CHOICES = [
        ("interne", "Interne"),
        ("externe_wilaya", "Externe Wilaya"),
        ("externe_secteur", "Externe Secteur"),
        ("externe_nationale", "Externe Nationale"),
    ]
    STATUT_CHOICES = [
        ("provisoire", "Provisoire"),
        ("definitive", "Définitive"),
    ]

    service_contractant_id = models.IntegerField(db_index=True)
    soumission = models.ForeignKey(
        Soumission,
        on_delete=models.CASCADE,
        db_column="soumission_id",
        related_name="attributions",
    )
    appel_id = models.IntegerField(db_index=True)
    commission_id = models.CharField(max_length=36, db_index=True, help_text="ID de la commission chargée de valider l'attribution — même valeur que AppelOffres.commission_id")
    validated_by = models.IntegerField(null=True, blank=True)
    validation_level = models.CharField(
        max_length=30,
        choices=VALIDATION_LEVEL_CHOICES,
        default="interne",
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default="provisoire",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attribution"