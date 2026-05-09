from django.urls import path

from .views import (
    ValidationListCreateView,
    ValidationRetrieveUpdateDeleteView,
    ValidationApproveView,
    ValidationRejectView,
    ContratListCreateView,
    ContratRetrieveUpdateDeleteView,
    ContratSignView,
    ContratDocumentsListView,
    ContratDocumentDetailView,
    SoumissionContratView,
    AffectationDetailView,
    ValidationTransmitView,
)

urlpatterns = [
    # Validations
    path("validations/", ValidationListCreateView.as_view()),
    path("validations/<int:validation_id>/", ValidationRetrieveUpdateDeleteView.as_view()),
    path("validations/<int:validation_id>/approuver/", ValidationApproveView.as_view()),
    path("validations/<int:validation_id>/rejeter/", ValidationRejectView.as_view()),

    # Contrats
    path("contrats", ContratListCreateView.as_view()),
    path("contrats/<int:contrat_id>", ContratRetrieveUpdateDeleteView.as_view()),
    path("contrats/<int:contrat_id>/signer", ContratSignView.as_view()),

    # Contrat documents
    path("contrats/<int:contrat_id>/documents", ContratDocumentsListView.as_view()),
    path("contrats/<int:contrat_id>/documents/<int:document_id>", ContratDocumentDetailView.as_view()),

    # Cross-entity
    path("soumissions/<int:soumission_id>/contrat", SoumissionContratView.as_view()),
    
    # --- ADDITION FOR AFFECTATION ---
    path("affectation-details/<int:soumission_id>/", AffectationDetailView.as_view()),
    path("transmettre-dossier/", ValidationTransmitView.as_view()),
]
