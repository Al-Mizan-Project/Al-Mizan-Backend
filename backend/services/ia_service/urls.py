from django.urls import path

from .views import (
    AnomalieDetailView,
    AnomalieListView,
    AnomalieParAppelView,
    AnomalieParSoumissionView,
    AnomalieStatutExamenPatchView,
    AnomaliesSummaryView,
    CdcRedigerView,
    CdcReviserView,
    DetecterAnomaliesAutoView,
    DetecterAnomaliesView,
    DetecterSaucissonnageAutoView,
    DetecterSaucissonnageView,
    VerifierConformiteSoumissionAutoView,
    AideRedactionView,
    VerifierConformiteSoumissionView,
)

urlpatterns = [
    # ── Collusion & Price-fixing Detection ──────────────────────────────
    path("ia/anomalies/detecter", DetecterAnomaliesView.as_view(), name="ia_anomalies_detecter"),
    path("ia/anomalies/detecter-auto", DetecterAnomaliesAutoView.as_view(), name="ia_anomalies_detecter_auto"),

    # ── Saucissonnage (Market Splitting) Detection ──────────────────────
    path("ia/saucissonnage/detecter", DetecterSaucissonnageView.as_view(), name="ia_saucissonnage_detecter"),
    path("ia/saucissonnage/detecter-auto", DetecterSaucissonnageAutoView.as_view(), name="ia_saucissonnage_detecter_auto"),

    # ── Anomaly Browsing & Management ───────────────────────────────────
    path("ia/anomalies", AnomalieListView.as_view(), name="ia_anomalies_list"),
    path("ia/anomalies/<int:anomalie_id>", AnomalieDetailView.as_view(), name="ia_anomalie_detail"),
    path("ia/anomalies/appel/<int:appel_id>", AnomalieParAppelView.as_view(), name="ia_anomalies_par_appel"),
    path("ia/anomalies/appel/<int:appel_id>/summary", AnomaliesSummaryView.as_view(), name="ia_anomalies_summary"),
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

    # ── Conformité ──────────────────────────────────────────────────────
    path(
        "ia/conformite/verifier-soumission/<int:soumission_id>",
        VerifierConformiteSoumissionView.as_view(),
        name="ia_conformite_verifier",
    ),
    path(
        "ia/conformite/verifier-soumission-auto/<int:soumission_id>",
        VerifierConformiteSoumissionAutoView.as_view(),
        name="ia_conformite_verifier_auto",
    ),

    # ── Cahier des Charges (CDC) ────────────────────────────────────────
    path("ia/cdc/rediger", CdcRedigerView.as_view(), name="ia_cdc_rediger"),
    path("ia/cdc/reviser", CdcReviserView.as_view(), name="ia_cdc_reviser"),
    
    
    
    
    path("aide-redaction/", AideRedactionView.as_view())
]