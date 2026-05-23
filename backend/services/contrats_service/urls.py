from django.urls import path

from .views import (
    # Validation (attributions provisoires)
    ValidationListCreateView,
    ValidationRetrieveUpdateDeleteView,
    ValidationApproveView,       # POST /validations/<id>/approuver/ → affecter validated_by
    ValidationRejectView,        # POST /validations/<id>/rejeter/   → valider (→ définitive)
    # New clean URLs for the same actions
    AffecterAttributionView,     # POST /validations/<id>/affecter/
    ValiderAttributionView,      # POST /validations/<id>/valider/
    # Contrats (attributions definitives)
    ContratListCreateView,
    ContratRetrieveUpdateDeleteView,
    ContratSignView,
    ContratDocumentsListView,
    ContratDocumentDetailView,
    # Cross-entity
    SoumissionContratView,
    AffectationDetailView,
    ValidationTransmitView,
)

urlpatterns = [
    # -----------------------------------------------------------------------
    # Validations  →  attributions provisoires
    # -----------------------------------------------------------------------

    # GET  /validations/?commission_id=X&validation_level=interne
    path("validations/", ValidationListCreateView.as_view()),

    # GET  /validations/<id>/   → détail complet enrichi
    path("validations/<int:validation_id>/", ValidationRetrieveUpdateDeleteView.as_view()),

    # POST /validations/<id>/approuver/  → affecter validated_by (legacy URL)
    path("validations/<int:validation_id>/approuver/", ValidationApproveView.as_view()),

    # POST /validations/<id>/rejeter/    → valider (→ definitive) (legacy URL)
    path("validations/<int:validation_id>/rejeter/", ValidationRejectView.as_view()),

    # New clean endpoints
    # POST /validations/<id>/affecter/   → assigner un membre (validated_by)
    path("validations/<int:validation_id>/affecter/", AffecterAttributionView.as_view()),

    # POST /validations/<id>/valider/    → membre confirme → statut = définitive
    path("validations/<int:validation_id>/valider/", ValiderAttributionView.as_view()),

    # -----------------------------------------------------------------------
    # Contrats  →  attributions definitives
    # -----------------------------------------------------------------------

    # GET  /contrats?service_contractant_id=X
    path("contrats", ContratListCreateView.as_view()),

    # GET  /contrats/<id>
    path("contrats/<int:contrat_id>", ContratRetrieveUpdateDeleteView.as_view()),

    # Legacy stubs (return 410 Gone)
    path("contrats/<int:contrat_id>/signer", ContratSignView.as_view()),
    path("contrats/<int:contrat_id>/documents", ContratDocumentsListView.as_view()),
    path("contrats/<int:contrat_id>/documents/<int:document_id>", ContratDocumentDetailView.as_view()),

    # -----------------------------------------------------------------------
    # Cross-entity
    # -----------------------------------------------------------------------

    # GET  /soumissions/<soumission_id>/contrat  → attribution définitive
    path("soumissions/<int:soumission_id>/contrat", SoumissionContratView.as_view()),

    # GET  /affectation-details/<soumission_id>/  → page d'affectation agrégée
    path("affectation-details/<int:soumission_id>/", AffectationDetailView.as_view()),

    # POST /transmettre-dossier/  → crée une attribution provisoire
    path("transmettre-dossier/", ValidationTransmitView.as_view()),
]
