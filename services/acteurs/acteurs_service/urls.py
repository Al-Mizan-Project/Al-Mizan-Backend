from django.urls import path

from .views import (
    MembreListCreateView,
    MembreRetrieveUpdateDeleteView,
    OperateurEconomiqueByNifView,
    OperateurEconomiqueListCreateView,
    OperateurEconomiqueRetrieveUpdateDeleteView,
    OrganisationListCreateView,
    OrganisationMembresView,
    OrganisationRetrieveUpdateDeleteView,
    ServiceContractantListCreateView,
    ServiceContractantMembresView,
    ServiceContractantRetrieveUpdateDeleteView,
    TutelleListCreateView,
    TutelleRetrieveUpdateDeleteView,
)

urlpatterns = [
    path("organisations", OrganisationListCreateView.as_view()),
    path("organisations/<int:organisation_id>", OrganisationRetrieveUpdateDeleteView.as_view()),
    path("organisations/<int:organisation_id>/membres", OrganisationMembresView.as_view()),
    path("services-contractants", ServiceContractantListCreateView.as_view()),
    path("services-contractants/<int:service_id>", ServiceContractantRetrieveUpdateDeleteView.as_view()),
    path("services-contractants/<int:service_id>/membres", ServiceContractantMembresView.as_view()),
    path("operateurs-economiques", OperateurEconomiqueListCreateView.as_view()),
    path("operateurs-economiques/<int:operateur_id>", OperateurEconomiqueRetrieveUpdateDeleteView.as_view()),
    path("operateurs-economiques/by-nif/<str:nif>", OperateurEconomiqueByNifView.as_view()),
    path("membres", MembreListCreateView.as_view()),
    path("membres/<int:membre_id>", MembreRetrieveUpdateDeleteView.as_view()),
    path("tutelles", TutelleListCreateView.as_view()),
    path("tutelles/<int:tutelle_id>", TutelleRetrieveUpdateDeleteView.as_view()),
]
