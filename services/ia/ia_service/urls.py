from django.urls import path

from .views import (
    AnomalieDetailView,
    AnomalieListView,
    AnomalieParAppelView,
    AnomalieParSoumissionView,
    AnomalieStatutExamenPatchView,
    CdcRedigerView,
    CdcReviserView,
    DetecterAnomaliesView,
    VerifierConformiteSoumissionView,
)

urlpatterns = [
    path("ia/anomalies/detecter", DetecterAnomaliesView.as_view(), name="ia_anomalies_detecter"),
    path("ia/anomalies", AnomalieListView.as_view(), name="ia_anomalies_list"),
    path("ia/anomalies/<int:anomalie_id>", AnomalieDetailView.as_view(), name="ia_anomalie_detail"),
    path("ia/anomalies/appel/<int:appel_id>", AnomalieParAppelView.as_view(), name="ia_anomalies_par_appel"),
    path(
        "ia/anomalies/soumission/<int:soumission_id>",
        AnomalieParSoumissionView.as_view(),
        name="ia_anomalies_par_soumission",
    ),
    path(
        "ia/anomalies/<int:anomalie_id>/statut-examen",
        AnomalieStatutExamenPatchView.as_view(),
        name="ia_anomalie_statut_examen",
    ),
    path(
        "ia/conformite/verifier-soumission/<int:soumission_id>",
        VerifierConformiteSoumissionView.as_view(),
        name="ia_conformite_verifier",
    ),
    path("ia/cdc/rediger", CdcRedigerView.as_view(), name="ia_cdc_rediger"),
    path("ia/cdc/reviser", CdcReviserView.as_view(), name="ia_cdc_reviser"),
]