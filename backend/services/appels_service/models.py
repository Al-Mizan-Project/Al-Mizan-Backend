from django.db import models


class AppelOffres(models.Model):
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("publie", "Publié"),
        ("depot_cloture", "Dépôt clôturé"),
        ("plis_ouverts", "Plis ouverts"),
        ("attribue", "Attribué"),
        ("annule", "Annulé"),
    ]

    id_appel_offres = models.AutoField(primary_key=True)
    id_service_contractant = models.IntegerField(db_index=True)
    reference = models.CharField(max_length=80, unique=True)
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    type_procedure = models.CharField(max_length=50)
    wilaya = models.CharField(max_length=80, blank=True, default="")
    montant_estime = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    date_publication = models.DateTimeField(null=True, blank=True)
    date_limite_soumission = models.DateTimeField(null=True, blank=True)
    date_ouverture_plis = models.DateTimeField(null=True, blank=True)
    poids_technique = models.IntegerField(default=50)
    poids_financier = models.IntegerField(default=50)
    required_docs_admin = models.JSONField(default=list, blank=True)
    required_docs_tech = models.JSONField(default=list, blank=True)
    required_docs_fin = models.JSONField(default=list, blank=True)
    minimum_revenue_da = models.IntegerField(default=0)
    qualification_category = models.CharField(max_length=120, blank=True, default="")
    minimum_experience_years = models.IntegerField(default=0)
    participation_conditions = models.JSONField(default=list, blank=True)
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default="brouillon")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appels_offres"


class DocumentsAppel(models.Model):
    id_document = models.IntegerField(db_index=True)
    id_appel_offres = models.ForeignKey(
        AppelOffres,
        on_delete=models.CASCADE,
        db_column="id_appel_offres",
        related_name="document_links",
    )

    class Meta:
        db_table = "documents_appel"
        constraints = [
            models.UniqueConstraint(
                fields=["id_document", "id_appel_offres"],
                name="unique_document_appel",
            ),
        ]


class AppelOffresSuivi(models.Model):
    id_appel_offres = models.ForeignKey(
        AppelOffres,
        on_delete=models.CASCADE,
        db_column="id_appel_offres",
        related_name="suivis",
    )
    id_utilisateur = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appels_offres_suivis"
        constraints = [
            models.UniqueConstraint(
                fields=["id_appel_offres", "id_utilisateur"],
                name="unique_appel_suivi_user",
            ),
        ]
