from django.db import models


class DetectionAnomalieIA(models.Model):
    """
    Stores detected anomalies from AI analysis.
    Each record represents a single anomaly flagged on a soumission 
    or appel d'offre by the detection algorithms.
    """

    class TypeAnomalie(models.TextChoices):
        # Collusion-related
        SIMILARITE_PRIX = "SIMILARITE_PRIX", "Similarité de prix"
        SIMILARITE_DOCUMENTAIRE = "SIMILARITE_DOCUMENTAIRE", "Similarité documentaire"
        COLLUSION_CLUSTER_PRIX = "COLLUSION_CLUSTER_PRIX", "Cluster de prix collusoire"
        ROTATION_SOUMISSIONNAIRES = "ROTATION_SOUMISSIONNAIRES", "Rotation de soumissionnaires"
        OFFRES_COMPLEMENTAIRES = "OFFRES_COMPLEMENTAIRES", "Offres de couverture"
        DISPERSION_ANORMALE = "DISPERSION_ANORMALE", "Dispersion anormale des prix"
        # Statistical outliers
        PRIX_ANORMALEMENT_BAS = "PRIX_ANORMALEMENT_BAS", "Prix anormalement bas"
        PRIX_ANORMALEMENT_ELEVE = "PRIX_ANORMALEMENT_ELEVE", "Prix anormalement élevé"
        BIAIS_NOMBRES_RONDS = "BIAIS_NOMBRES_RONDS", "Biais de nombres ronds"
        # Saucissonnage
        SAUCISSONNAGE_PROXIMITE_SEUIL = "SAUCISSONNAGE_PROXIMITE_SEUIL", "Proximité de seuil réglementaire"
        SAUCISSONNAGE_TEMPOREL = "SAUCISSONNAGE_TEMPOREL", "Clustering temporel suspect"
        SAUCISSONNAGE_CUMUL_SEUIL = "SAUCISSONNAGE_CUMUL_SEUIL", "Dépassement cumulé de seuil"
        SAUCISSONNAGE_MEME_FOURNISSEUR = "SAUCISSONNAGE_MEME_FOURNISSEUR", "Même fournisseur multi-marchés"

    class NiveauSeverite(models.TextChoices):
        CRITIQUE = "CRITIQUE", "Critique"
        ELEVEE = "ELEVEE", "Élevée"
        MOYEN = "MOYEN", "Moyen"
        FAIBLE = "FAIBLE", "Faible"

    class StatutExamen(models.TextChoices):
        A_REVOIR = "A_REVOIR", "À revoir"
        EN_COURS = "EN_COURS", "En cours d'examen"
        CONFIRMEE = "CONFIRMEE", "Confirmée"
        REJETEE = "REJETEE", "Rejetée (faux positif)"
        SIGNALEE = "SIGNALEE", "Signalée à la tutelle"

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
        default=StatutExamen.A_REVOIR,
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