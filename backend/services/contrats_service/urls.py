from django.urls import path

from .views import (
    AttributionProvisoireListView,
    AttributionDetailView,
    AffecterAttributionView,
    ValiderAttributionView,
    AttributionDefinitiveListView,
    AttributionDefinitiveDetailView,
)

urlpatterns = [
    # -----------------------------------------------------------------------
    # Validations  →  attributions provisoires
    # -----------------------------------------------------------------------

    # GET  /attributions-provisoires/?commission_id=X&validation_level=interne
    path("attributions-provisoires/", AttributionProvisoireListView.as_view()),



    # GET  /attributions-provisoires/<id>/   → détail complet enrichi
    path("attributions-provisoires/<int:attribution_provisoire_id>/", AttributionDetailView.as_view()),

    # POST /attributions-provisoires/<id>/affecter/  → affecter validated_by
    path("attributions-provisoires/<int:attribution_provisoire_id>/affecter/", AffecterAttributionView.as_view()),

    # POST /attributions-provisoires/<id>/valider/    → valider (→ definitive)
    path("attributions-provisoires/<int:attribution_provisoire_id>/valider/", ValiderAttributionView.as_view()),

    # -----------------------------------------------------------------------
    # Contrats  →  attributions definitives
    # -----------------------------------------------------------------------

    # GET  /attributions-definitives?service_contractant_id=X
    path("attributions-definitives/", AttributionDefinitiveListView.as_view()),

    # GET  /attributions-definitives/<id>
    path("attributions-definitives/<int:attribution_definitive_id>/", AttributionDefinitiveDetailView.as_view()),


]
