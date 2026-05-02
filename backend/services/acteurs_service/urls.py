from django.urls import path
from .views import (
    DemandeOperateurListView, DemandeOperateurDetailView, DemandeApprouverView,
    CreerServiceContractantView, ListServiceContractantView,
    CreerCommissionExterneView, ListCommissionExterneView,
    CreerTutelleView, ListTutelleView,
    ListOperateurEconomiqueView,
    CreerResponsableView, CreateMembreByResponsableView, MembreDetailView ,ListMembresOrganisationView , SoumettreDemandeOperateurView
)

urlpatterns = [
    # ==========================================
    # 0. INSCRIPTION OPÉRATEUR ÉCONOMIQUE (Public)
    # ==========================================
    path('demandes/soumettre/', SoumettreDemandeOperateurView.as_view(), name='soumettre-demande-operateur'),
    # ==========================================
    # 1. GESTION DES DEMANDES (Opérateurs Économiques)
    # ==========================================
    path('admin/demandes/', DemandeOperateurListView.as_view(), name='admin-liste-demandes'),
    path('admin/demandes/<uuid:id>/', DemandeOperateurDetailView.as_view(), name='admin-detail-demande'),
    path('admin/demandes/<uuid:id>/approuver/', DemandeApprouverView.as_view(), name='admin-approuver-demande'),
    
    # ==========================================
    # 2. GESTION DES ORGANISATIONS (Par l'Admin)
    # ==========================================
    # --- Service Contractant ---
    path('admin/organisations/service-contractant/creer/', CreerServiceContractantView.as_view(), name='admin-creer-service-contractant'),
    path('admin/organisations/service-contractant/', ListServiceContractantView.as_view(), name='list-service-contractant'),
    
    # --- Commission Externe ---
    path('admin/organisations/commission-externe/creer/', CreerCommissionExterneView.as_view(), name='admin-creer-commission-externe'),
    path('admin/organisations/commission-externe/', ListCommissionExterneView.as_view(), name='list-commission-externe'),
    
    # --- Tutelle ---
    path('admin/organisations/tutelle/creer/', CreerTutelleView.as_view(), name='admin-creer-tutelle'),
    path('admin/organisations/tutelle/', ListTutelleView.as_view(), name='list-tutelle'),
    
    # --- Opérateurs Économiques (Listing seul, car créés via l'approbation) ---
    path('admin/organisations/operateurs/', ListOperateurEconomiqueView.as_view(), name='list-operateurs'),

    # ==========================================
    # 3. GESTION DES MEMBRES & RESPONSABLES
    # ==========================================
    
    path('membres/<uuid:id_membre>/', MembreDetailView.as_view(), name='detail-membre'),
    # Création du responsable principal (Par l'Admin)
    path('organisations/<uuid:org_id>/responsable/', CreerResponsableView.as_view(), name='creer-responsable-organisation'),
    
    # Listing des membres d'une organisation
    path('organisations/<uuid:org_id>/membres/', ListMembresOrganisationView.as_view(), name='liste-membres-organisation'),
    
    # Création d'un collaborateur (Par le Responsable)
    path('membres/creer-collaborateur/', CreateMembreByResponsableView.as_view(), name='responsable-creer-membre'),
]