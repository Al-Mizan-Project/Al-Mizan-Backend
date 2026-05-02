from django.db import models


class DetectionAnomalieIA(models.Model):
    """
    Stores detected anomalies from AI analysis.
    Each record represents a single anomaly flagged on a soumission 
    or appel d'offre by the detection algorithms.
    """

    class TypeAnomalie(models.TextChoices):
        # Single-soumission rules
        MONTANT_FINANCIER_MANQUANT = "MONTANT_FINANCIER_MANQUANT", "Montant financier manquant"
        MONTANT_INVALID = "MONTANT_INVALID", "Montant invalide"
        MONTANT_TROP_ELEVE = "MONTANT_TROP_ELEVE", "Montant trop élevé"
        MONTANT_TROP_BAS = "MONTANT_TROP_BAS", "Montant trop bas"
        SOUMISSION_HORS_DELAI = "SOUMISSION_HORS_DELAI", "Soumission hors délai"
        # Statistical outliers (multi-soumission)
        PRIX_ANORMALEMENT_BAS = "PRIX_ANORMALEMENT_BAS", "Prix anormalement bas"
        PRIX_ANORMALEMENT_ELEVE = "PRIX_ANORMALEMENT_ELEVE", "Prix anormalement élevé"
        DISPERSION_ANORMALE = "DISPERSION_ANORMALE", "Dispersion anormale des prix"
        ROTATION_SOUMISSIONNAIRES = "ROTATION_SOUMISSIONNAIRES", "Rotation de soumissionnaires"
        # Saucissonnage
        SAUCISSONNAGE_PROXIMITE_SEUIL = "SAUCISSONNAGE_PROXIMITE_SEUIL", "Proximité de seuil réglementaire"
        SAUCISSONNAGE_TEMPOREL = "SAUCISSONNAGE_TEMPOREL", "Clustering temporel suspect"
        SAUCISSONNAGE_CUMUL_SEUIL = "SAUCISSONNAGE_CUMUL_SEUIL", "Dépassement cumulé de seuil"
        SAUCISSONNAGE_MEME_FOURNISSEUR = "SAUCISSONNAGE_MEME_FOURNISSEUR", "Même fournisseur multi-marchés"

    class NiveauSeverite(models.TextChoices):
        ERROR = "ERROR", "Erreur"
        WARNING = "WARNING", "Avertissement"

    class StatutExamen(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        EN_COURS = "EN_COURS", "En cours d'examen"
        VALIDE = "VALIDE", "Validé"
        REJETE = "REJETE", "Rejeté (faux positif)"
        SIGNALE = "SIGNALE", "Signalé à la tutelle"

    id_detection_anomalie_ia = models.AutoField(primary_key=True)
    id_appel_offre = models.IntegerField(db_index=True)
    id_soumission = models.IntegerField(null=True, blank=True, db_index=True)
    type_anomalie = models.CharField(
        max_length=50,
        choices=TypeAnomalie.choices,
        db_index=True,
    )
    niveau_severite = models.CharField(
        max_length=20,
        choices=NiveauSeverite.choices,
    )
    score_confiance = models.DecimalField(max_digits=5, decimal_places=2)
    details = models.TextField(blank=True, default="")
    soumissions_impliquees = models.JSONField(
        blank=True,
        null=True,
        help_text="List of soumission IDs involved in this anomaly pattern",
    )
    appels_impliques = models.JSONField(
        blank=True,
        null=True,
        help_text="List of appel d'offre IDs involved (for saucissonnage)",
    )
    statut_examen = models.CharField(
        max_length=30,
        choices=StatutExamen.choices,
        default=StatutExamen.EN_ATTENTE,
    )
    examiné_par = models.IntegerField(
        null=True,
        blank=True,
        help_text="User ID who reviewed this anomaly",
    )
    commentaire_examen = models.TextField(
        blank=True,
        default="",
        help_text="Reviewer's comment on the anomaly",
    )
    date_detection = models.DateTimeField(auto_now_add=True)
    date_examen = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "detection_anomalie_ia"
        ordering = ["-date_detection", "-id_detection_anomalie_ia"]
        indexes = [
            models.Index(fields=["id_appel_offre", "type_anomalie"], name="idx_appel_type"),
            models.Index(fields=["statut_examen", "niveau_severite"], name="idx_statut_severite"),
        ]

    def __str__(self):
        return (
            f"Anomalie #{self.id_detection_anomalie_ia} "
            f"[{self.type_anomalie}] - Appel #{self.id_appel_offre}"
        )