from django.urls import path

from .views import (
    AppelOffresDocumentDetailView,
    AppelOffresDocumentsView,
    AppelOffresListCreateView,
    AppelOffresRetrieveUpdateDeleteView,
    AppelOffresPublierView,
    AppelOffresCloturerDepotView,
    AppelOffresOuvrirPlisView,
    AppelOffresAnnulerView,
    ServiceContractantAppelsView,
)

urlpatterns = [
    # Appels offres – CRUD
    path("appels-offres", AppelOffresListCreateView.as_view()),
    path("appels-offres/<int:appel_id>", AppelOffresRetrieveUpdateDeleteView.as_view()),
    # Appels offres – workflow actions
    path("appels-offres/<int:appel_id>/publier", AppelOffresPublierView.as_view()),
    path("appels-offres/<int:appel_id>/cloturer-depot", AppelOffresCloturerDepotView.as_view()),
    path("appels-offres/<int:appel_id>/ouvrir-plis", AppelOffresOuvrirPlisView.as_view()),
    path("appels-offres/<int:appel_id>/annuler", AppelOffresAnnulerView.as_view()),
    # Appels offres – documents
    path("appels-offres/<int:appel_id>/documents", AppelOffresDocumentsView.as_view()),
    path("appels-offres/<int:appel_id>/documents/<int:document_id>", AppelOffresDocumentDetailView.as_view()),
    # Filter by service contractant
    path("services-contractants/<int:service_id>/appels-offres", ServiceContractantAppelsView.as_view()),
]
