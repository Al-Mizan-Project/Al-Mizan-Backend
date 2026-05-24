from django.db import models


class ComissionEvaluation(models.Model):
    id_comission = models.AutoField(primary_key=True)
    id_service = models.IntegerField()
    nom_comission = models.CharField(max_length=255)
    categorie = models.CharField(max_length=255)
    # Display-only label fields — no permission difference between members
    ROLE_LABEL_CHOICES = [
        ('president', 'Président de séance'),
        ('secretaire', 'Secrétaire'),
        ('membre', 'Membre'),
    ]

    class Meta:
        db_table = "comission_evaluation"


class MembresCommissionEvaluation(models.Model):
    id_comission = models.ForeignKey(
        ComissionEvaluation,
        on_delete=models.CASCADE,
        db_column="id_comission",
        related_name="membres"
    )
    id_utilisateur = models.IntegerField()
    # Display-only label — zero permission difference per process spec
    role_label = models.CharField(
        max_length=20,
        choices=[('president', 'Président de séance'), ('secretaire', 'Secrétaire'), ('membre', 'Membre')],
        default='membre'
    )

    class Meta:
        db_table = "membres_commission_evaluation"
        constraints = [
            models.UniqueConstraint(
                fields=["id_comission", "id_utilisateur"],
                name="unique_membre_commission"
            )
        ]


# ── Step 1: Reception register ────────────────────────────────────────────────

class RegistreReception(models.Model):
    """One row per soumission in the reception register for a given appel."""
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="registre_entries"
    )
    id_soumission = models.IntegerField()
    numero_ordre = models.IntegerField()  # sequential reception number
    nom_oe = models.CharField(max_length=255)
    received_at = models.DateTimeField()
    submitted_at = models.DateTimeField()
    hors_delai = models.BooleanField(default=False)  # auto-flagged if received after deadline

    class Meta:
        db_table = "registre_reception"
        unique_together = [["id_comission", "id_soumission"]]


class RegistreIntegriteConfirmation(models.Model):
    """Locks the register — created when COPEO clicks 'Confirmer l'intégrité'."""
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="integrite_confirmations"
    )
    confirmed_by = models.IntegerField()  # id_utilisateur
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registre_integrite_confirmation"
        # Only one confirmation per commission
        constraints = [
            models.UniqueConstraint(fields=["id_comission"], name="unique_integrite_commission")
        ]


# ── Step 2: Opening session ───────────────────────────────────────────────────

class SeanceOuverture(models.Model):
    """The live opening session — one per commission per appel."""
    STATUT_CHOICES = [
        ('not_started', 'Non démarrée'),
        ('in_progress', 'En cours'),
        ('closed', 'Clôturée'),
    ]
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="seances"
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='not_started')
    started_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # Anomaly log — recorded if session starts outside published time window
    anomalie = models.TextField(blank=True, default="")

    class Meta:
        db_table = "seance_ouverture"
        constraints = [
            models.UniqueConstraint(fields=["id_comission"], name="unique_seance_commission")
        ]


class PliOuverture(models.Model):
    """One row per pli (soumission) opened during the session."""
    seance = models.ForeignKey(SeanceOuverture, on_delete=models.CASCADE, related_name="plis")
    id_soumission = models.IntegerField()
    opened_at = models.DateTimeField(null=True, blank=True)
    montant_declare = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "pli_ouverture"
        unique_together = [["seance", "id_soumission"]]


class ParapheMembre(models.Model):
    """Each COPEO member must paraph each opened pli."""
    pli = models.ForeignKey(PliOuverture, on_delete=models.CASCADE, related_name="paraphes")
    id_utilisateur = models.IntegerField()
    paraphed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "paraphe_membre"
        unique_together = [["pli", "id_utilisateur"]]


# ── Step 3: Conformité ────────────────────────────────────────────────────────

class ConformiteOffer(models.Model):
    """Formal conformity + eligibility result per soumission."""
    RESULTAT_CHOICES = [
        ('admis', 'Admis'),
        ('ecarte', 'Écarté'),
    ]
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="conformites"
    )
    id_soumission = models.IntegerField()
    # 3A checklist
    enveloppe_anonyme = models.BooleanField(null=True)
    documents_corrects = models.BooleanField(null=True)
    pas_prix_technique = models.BooleanField(null=True)
    # 3B eligibility
    eligible_art75 = models.BooleanField(null=True)
    # Complement request
    complement_demande = models.BooleanField(default=False)
    complement_motif = models.TextField(blank=True, default="")
    # Final result
    resultat = models.CharField(max_length=10, choices=RESULTAT_CHOICES, null=True, blank=True)
    motif_ecart = models.TextField(blank=True, default="")

    class Meta:
        db_table = "conformite_offer"
        unique_together = [["id_comission", "id_soumission"]]


# ── Step 4: Capacités ─────────────────────────────────────────────────────────

class CapacitesOffer(models.Model):
    """Minimum capacities check per soumission."""
    RESULTAT_CHOICES = [
        ('suffisant', 'Capacités suffisantes'),
        ('insuffisant', 'Capacités insuffisantes'),
    ]
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="capacites"
    )
    id_soumission = models.IntegerField()
    # JSON dict of item_id -> bool result
    items_results = models.JSONField(default=dict)
    justification = models.TextField(blank=True, default="")
    resultat = models.CharField(max_length=15, choices=RESULTAT_CHOICES, null=True, blank=True)
    motif = models.TextField(blank=True, default="")

    class Meta:
        db_table = "capacites_offer"
        unique_together = [["id_comission", "id_soumission"]]


# ── Step 5: Technical evaluation ─────────────────────────────────────────────

class EvalTechniqueOffer(models.Model):
    """Technical scoring per soumission — SC criteria applied, scores locked after validation."""
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="evals_technique"
    )
    id_soumission = models.IntegerField()
    # scores: {criterion_id: score_value}
    scores = models.JSONField(default=dict)
    # justifications: {criterion_id: text} — mandatory per criterion
    justifications = models.JSONField(default=dict)
    score_total = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    qualifie = models.BooleanField(null=True)  # True if score >= SC threshold
    locked = models.BooleanField(default=False)  # once locked, no retroactive changes

    class Meta:
        db_table = "eval_technique_offer"
        unique_together = [["id_comission", "id_soumission"]]


# ── Step 6: Financial evaluation ──────────────────────────────────────────────

class EvalFinanciereOffer(models.Model):
    """Financial evaluation — arithmetic check, correction, marge de préférence."""
    CORRECTION_RULE_CHOICES = [
        ('unit_price', 'Prix unitaire prévaut'),
        ('total', 'Total déclaré prévaut'),
    ]
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="evals_financiere"
    )
    id_soumission = models.IntegerField()
    montant_declare = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    montant_bpu_calcule = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    correction_rule = models.CharField(max_length=15, choices=CORRECTION_RULE_CHOICES, null=True, blank=True)
    montant_corrige = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    # Marge de préférence — auto-applied +25% for foreign OE
    marge_appliquee = models.BooleanField(default=False)
    montant_evaluation = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    # If OE refuses correction
    refuse_correction = models.BooleanField(default=False)
    refuse_motif = models.TextField(blank=True, default="")
    locked = models.BooleanField(default=False)

    class Meta:
        db_table = "eval_financiere_offer"
        unique_together = [["id_comission", "id_soumission"]]


# ── Step 7: Classement ────────────────────────────────────────────────────────

class ClassementEntry(models.Model):
    """Final ranking entry — one row per soumission per commission."""
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="classement"
    )
    id_soumission = models.IntegerField()
    rang = models.IntegerField()
    score_technique = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    score_financier = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    score_combine = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    # Whether this soumission was eliminated after being provisional winner
    ecarte_provisoire = models.BooleanField(default=False)
    motif_ecart = models.TextField(blank=True, default="")

    class Meta:
        db_table = "classement_entry"
        unique_together = [["id_comission", "id_soumission"]]


# ── Step 8: PV ───────────────────────────────────────────────────────────────

class ProcesVerbal(models.Model):
    """PV Ouverture or PV Evaluation — one per type per commission."""
    TYPE_CHOICES = [
        ('ouverture', 'PV Ouverture'),
        ('evaluation', 'PV Évaluation'),
    ]
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="pvs"
    )
    type_pv = models.CharField(max_length=15, choices=TYPE_CHOICES)
    locked = models.BooleanField(default=False)
    sent_to_sc = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proces_verbal"
        unique_together = [["id_comission", "type_pv"]]


class SignaturePV(models.Model):
    """Each COPEO member signs the PV — reserve text is their outlet for disagreement."""
    pv = models.ForeignKey(ProcesVerbal, on_delete=models.CASCADE, related_name="signatures")
    id_utilisateur = models.IntegerField()
    reserve = models.TextField(blank=True, default="")
    has_reserve = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "signature_pv"
        unique_together = [["pv", "id_utilisateur"]]


class SCDecision(models.Model):
    """SC decision after receiving both PVs."""
    DECISION_CHOICES = [
        ('accepted', 'Accepté — Attribution provisoire'),
        ('rejected', 'Rejeté'),
        ('info_request', 'Demande d\'informations complémentaires'),
    ]
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE, related_name="sc_decisions"
    )
    decision = models.CharField(max_length=15, choices=DECISION_CHOICES)
    motif_rejet = models.TextField(blank=True, default="")  # mandatory if rejected, auditable
    decided_by = models.IntegerField()  # id_utilisateur SC
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sc_decision"


# ── Keep original Evaluation table for raw score storage (backward compat) ───

class Evaluation(models.Model):
    EVALUATION_TYPES = [
        ("administrative", "Administrative"),
        ("technique", "Technique"),
        ("financiere", "Financière")
    ]
    id_evalution = models.AutoField(primary_key=True)
    id_comission = models.ForeignKey(
        ComissionEvaluation, on_delete=models.CASCADE,
        db_column="id_comission", related_name="evaluations"
    )
    id_soumission = models.IntegerField()
    id_utilisateur = models.IntegerField()
    type = models.CharField(max_length=20, choices=EVALUATION_TYPES)
    note = models.IntegerField()
    commentaire = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "evaluation"
        constraints = [
            models.UniqueConstraint(
                fields=["id_comission", "id_soumission", "id_utilisateur", "type"],
                name="unique_evaluation_par_membre"
            )
        ]