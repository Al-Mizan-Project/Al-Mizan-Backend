from django.db import models


class AppelOffres(models.Model):
    TYPE_PRESTATION_CHOICES = [
        ("travaux", "Travaux"),
        ("fournitures", "Fournitures"),
        ("services", "Services"),
        ("etudes", "Etudes"),
    ]
    VISIBILITE_CHOICES = [
        ("public", "Public"),
        ("prive", "Prive"),
    ]
    # NOUVEAU : Liste des statuts mise à jour selon vos exigences
    STATUT_CHOICES = [
        ("non_valide", "Non validé"),
        ("valide", "Validé"),
        ("refuse", "Refusé"),
        ("ferme", "Fermé"),
    ]
    # NOUVEAU : Liste des niveaux de validation requis
    VALIDATION_LEVEL_CHOICES = [
        ("interne", "Interne"),
        ("externe_wilaya", "Externe Wilaya"),
        ("externe_secteur", "Externe Secteur"),
        ("externe_nationale", "Externe Nationale"),
    ]

    id_appel_offres = models.AutoField(primary_key=True)
    id_service_contractant = models.IntegerField(db_index=True)
    
    # NOUVEAUX ATTRIBUTS (Microservices)
    commission_id = models.IntegerField(db_index=True, help_text="ID de la commission provenant du service externe")
    validated_by = models.IntegerField(db_index=True, null=True, blank=True, help_text="ID du membre ayant validé la demande")
    validation_level = models.CharField(
        max_length=30,
        choices=VALIDATION_LEVEL_CHOICES,
        default="interne"
    )

    reference = models.CharField(max_length=80, unique=True)
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    type_procedure = models.CharField(max_length=50)
    type_prestation = models.CharField(
        max_length=20,
        choices=TYPE_PRESTATION_CHOICES,
        default="travaux",
    )
    visibilite = models.CharField(
        max_length=10,
        choices=VISIBILITE_CHOICES,
        default="public",
    )
    wilaya = models.CharField(max_length=80, blank=True, default="")
    localisation = models.CharField(max_length=255, blank=True, default="")
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
    
    # MODIFIÉ : Statut par défaut configuré sur "non_valide"
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default="non_valide")
    
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


class AppelOffresOperateurInvite(models.Model):
    STATUT_INVITATION_CHOICES = [
        ("invite", "Invite"),
        ("a_repondu", "A repondu"),
        ("retire", "Retire"),
    ]

    id_appel_offres = models.ForeignKey(
        AppelOffres,
        on_delete=models.CASCADE,
        db_column="id_appel_offres",
        related_name="operateurs_invites",
    )
    id_operateur_economique = models.IntegerField(db_index=True)
    statut_invitation = models.CharField(
        max_length=30,
        choices=STATUT_INVITATION_CHOICES,
        default="invite",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appels_offres_operateurs_invites"
        constraints = [
            models.UniqueConstraint(
                fields=["id_appel_offres", "id_operateur_economique"],
                name="unique_appel_operateur_invite",
            ),
        ]


class AchatSimple(models.Model):
    TYPE_PRESTATION_CHOICES = AppelOffres.TYPE_PRESTATION_CHOICES
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("valide", "Valide"),
        ("engage", "Engage"),
        ("annule", "Annule"),
    ]

    id_achat_simple = models.AutoField(primary_key=True)
    id_service_contractant = models.IntegerField(db_index=True)
    reference = models.CharField(max_length=80, unique=True)
    objet = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    type_prestation = models.CharField(
        max_length=20,
        choices=TYPE_PRESTATION_CHOICES,
        default="fournitures",
    )
    wilaya = models.CharField(max_length=80, blank=True, default="")
    localisation = models.CharField(max_length=255, blank=True, default="")
    montant_estime = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    id_operateur_economique = models.IntegerField(null=True, blank=True, db_index=True)
    date_demande = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default="brouillon")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "achats_simples"


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