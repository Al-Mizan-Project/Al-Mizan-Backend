from django.urls import path

from .views import (
    AchatSimpleListCreateView,
    AchatSimpleRetrieveUpdateDeleteView,
    AppelOffresDocumentDetailView,
    AppelOffresDocumentsView,
    AppelOffresListCreateView,
    AppelOffresRetrieveUpdateDeleteView,
    AppelOffresPublierView,
    AppelOffresCloturerDepotView,
    AppelOffresOuvrirPlisView,
    AppelOffresAnnulerView,
    AppelOffresSoumettreValidationView,
    AppelOffresValiderView,
    AppelOffresRefuserView,
    AppelOffresAffectValidatorView,
    ServiceContractantAppelsView,
    ServiceContractantAchatsSimplesView,
    UserWatchedAppelDetailView,
    UserWatchedAppelsView,
    CommissionInterneDossiersView,
    CommissionExterneDossiersView,
    CommissionAppelsUnifiedView,
)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class CacheFlushView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        from .services.cache import bump_cache_version
        bump_cache_version()
        return Response({"status": "cache flushed"})

urlpatterns = [
    
    # Achats simples - dedicated endpoints
    path("achats-simples", AchatSimpleListCreateView.as_view()),
    path("achats-simples/<int:achat_id>", AchatSimpleRetrieveUpdateDeleteView.as_view()),
    # Appels offres – CRUD
    path("appels-offres", AppelOffresListCreateView.as_view()),
    path("appels-offres/<int:appel_id>", AppelOffresRetrieveUpdateDeleteView.as_view()),
    # Appels offres – workflow actions
    path("appels-offres/<int:appel_id>/soumettre-validation", AppelOffresSoumettreValidationView.as_view()),
    path("appels-offres/<int:appel_id>/valider", AppelOffresValiderView.as_view()),
    path("appels-offres/<int:appel_id>/affecter-validateur", AppelOffresAffectValidatorView.as_view()),
    path("appels-offres/<int:appel_id>/refuser", AppelOffresRefuserView.as_view()),
    path("appels-offres/<int:appel_id>/publier", AppelOffresPublierView.as_view()),
    path("appels-offres/<int:appel_id>/cloturer-depot", AppelOffresCloturerDepotView.as_view()),
    path("appels-offres/<int:appel_id>/ouvrir-plis", AppelOffresOuvrirPlisView.as_view()),
    path("appels-offres/<int:appel_id>/annuler", AppelOffresAnnulerView.as_view()),
    # Appels offres – documents
    path("appels-offres/<int:appel_id>/documents", AppelOffresDocumentsView.as_view()),
    path("appels-offres/<int:appel_id>/documents/<int:document_id>", AppelOffresDocumentDetailView.as_view()),
    # Filter by service contractant
    path("services-contractants/<int:service_id>/appels-offres", ServiceContractantAppelsView.as_view()),
    path("services-contractants/<int:service_id>/achats-simples", ServiceContractantAchatsSimplesView.as_view()),
    # User watched appels
    path("users/<int:user_id>/appels-offres/suivis", UserWatchedAppelsView.as_view()),
    path("users/<int:user_id>/appels-offres/<int:appel_id>/suivi", UserWatchedAppelDetailView.as_view()),
    # Commission Interne
    path("appels-offres/commission-interne/dossiers", CommissionInterneDossiersView.as_view()),
    # Commission Externe
    path("appels-offres/commission-externe/dossiers", CommissionExterneDossiersView.as_view()),
    # Commission Unified (new)
    path("appels-offres/commission/dossiers", CommissionAppelsUnifiedView.as_view()),
    # Cache flush utility
    path("cache/flush", CacheFlushView.as_view()),
]
