import uuid
from django.db import models

# ==========================================
# 1. ÉNUMÉRATIONS (CHOICES)
# ==========================================

class StatutDemande(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    APPROUVE = 'APPROUVE', 'Approuvé'
    REJETE = 'REJETE', 'Rejeté'

class TypeDocument(models.TextChoices):
    REGISTRE_COMMERCE = 'REGISTRE_COMMERCE', 'Registre de commerce'
    NIF = 'NIF', 'Carte fiscale (NIF)'
    CNAS_CASNOS = 'CNAS_CASNOS', 'Attestation CNAS / CASNOS'
    NON_FAILLITE = 'NON_FAILLITE', 'Certificat de non-faillite'

class TypeEntite(models.TextChoices):
    OPERATEUR_ECONOMIQUE = 'OPERATEUR_ECONOMIQUE', 'Opérateur Économique'
    SERVICE_CONTRACTANT = 'SERVICE_CONTRACTANT', 'Service Contractant'
    COMMISSION_EXTERNE = 'COMMISSION_EXTERNE', 'Commission Externe'
    TUTELLE = 'TUTELLE', 'Tutelle'


# ==========================================
# 2. PHASE D'INSCRIPTION (SAS D'ATTENTE)
# ==========================================

class DemandeOperateur(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom_organisation = models.CharField(max_length=255, default="Non renseigné")
    email_contact = models.EmailField(default="contact@defaut.dz")
    telephone = models.CharField(max_length=50, default="0000000000")
    
    # Informations spécifiques à l'opérateur
    nif = models.CharField(max_length=50, default="000000000000000")
    num_registre_commerce = models.CharField(max_length=100, default="RC-DEFAULT")
    
    statut = models.CharField(
        max_length=20, 
        choices=StatutDemande.choices, 
        default=StatutDemande.EN_ATTENTE
    )
    motif_rejet = models.TextField(blank=True, default="")
    
    cree_le = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom_organisation} - {self.get_statut_display()}"


class DemandeDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    demande = models.ForeignKey(DemandeOperateur, on_delete=models.CASCADE, related_name='documents')
    
    document_id = models.IntegerField(help_text="ID du fichier dans le service Document", default=0) 
    
    type_document = models.CharField(
        max_length=30, 
        choices=TypeDocument.choices,
        default=TypeDocument.REGISTRE_COMMERCE
    )


# ==========================================
# 3. PHASE POST-APPROBATION (ENTITÉS DÉFINITIVES)
# ==========================================

class Organisation(models.Model):
    id_organisation = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    nom_officiel = models.CharField(max_length=255, default="Organisation Anonyme") 
    adresse_siege = models.CharField(max_length=100, blank=True, null=True, default="")
    email_contact = models.CharField(max_length=100, blank=True, null=True, default="")
    type_entite = models.CharField(
        max_length=30, 
        choices=TypeEntite.choices,
        default=TypeEntite.OPERATEUR_ECONOMIQUE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "organisation"

    def __str__(self):
        return f"{self.nom_officiel} ({self.get_type_entite_display()})"


class OperateurEconomique(models.Model):
    organisation = models.OneToOneField(
        Organisation, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name='operateur_economique'
    )
    nif = models.CharField(max_length=50, default="000000000000000")
    num_registre_commerce = models.CharField(max_length=100, default="RC-DEFAULT")
    
    def __str__(self):
        return self.organisation.nom_officiel


class ServiceContractant(models.Model):
    organisation = models.OneToOneField(
        Organisation, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name='service_contractant'
    )
    # Champs spécifiques ajoutés avec valeurs par défaut
    code_service = models.CharField(max_length=50, default="SC-000")
    secteur_activite = models.CharField(max_length=100, default="Non défini")
    
    def __str__(self):
        return self.organisation.nom_officiel


class CommissionExterne(models.Model):
    organisation = models.OneToOneField(
        Organisation, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name='commission_externe'
    )
    # Champs spécifiques ajoutés avec valeurs par défaut
    numero_agrement = models.CharField(max_length=50, default="AGR-000")
    specialite = models.CharField(max_length=100, default="Générale")
    
    def __str__(self):
        return self.organisation.nom_officiel


class Tutelle(models.Model):
    organisation = models.OneToOneField(
        Organisation, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name='tutelle'
    )
    # Champs spécifiques ajoutés avec valeurs par défaut
    ministere_attache = models.CharField(max_length=150, default="Ministère non assigné")
    
    def __str__(self):
        return self.organisation.nom_officiel


# ==========================================
# 4. MEMBRES DE L'ORGANISATION
# ==========================================

class Membre(models.Model):
    id_membre = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey('Organisation', on_delete=models.CASCADE, related_name='membres', null=True)
    
    nom = models.CharField(max_length=100, default="Anonyme")
    prenom = models.CharField(max_length=100, default="Anonyme")
    telephone = models.CharField(max_length=30, blank=True, null=True, default="")
    fonction = models.CharField(max_length=50, blank=True, null=True, default="Employé")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "membre"

    def __str__(self):
        return f"{self.prenom} {self.nom}"
