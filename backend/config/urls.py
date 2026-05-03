from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from soumissions_app.views import (
    AppelOffreSoumissionsView,
    EvaluationCreateView,
    OpenBidsView,
    OperateurSoumissionsView,
    SoumissionConformitePatchView,
    SoumissionCreateView,
    SoumissionDetailView,
    SoumissionDocumentsView,
    SoumissionTerminerEvaluationView,
    SoumissionWithdrawView,
)
from shared.health import HealthView, ReadyView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", HealthView.as_view()),
    path("ready", ReadyView.as_view()),
    path(
        "openapi.json",
        SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]),
        name="openapi-schema",
    ),
    path(
        "docs/swagger/",
        SpectacularSwaggerView.as_view(
            url_name="openapi-schema",
            permission_classes=[AllowAny],
            authentication_classes=[],
        ),
        name="swagger-ui",
    ),
    path(
        "docs/redoc/",
        SpectacularRedocView.as_view(
            url_name="openapi-schema",
            permission_classes=[AllowAny],
            authentication_classes=[],
        ),
        name="redoc",
    ),
    path("", include("auth_service.urls")),
    path("", include("acteurs_service.urls")),
    path("", include("contractant_service.urls")),
    path("", include("appels_service.urls")),
    path("", include("evaluations_service.urls")),
    path("", include("contrats_service.urls")),
    path("", include("notifications_service.urls")),
    path("", include("ia_service.urls")),
    path("", include("documents_service.urls")),
    path("api/soumissions/", include("soumissions_app.urls")),
    path("soumissions", SoumissionCreateView.as_view()),
    path("soumissions/<int:soumission_id>", SoumissionDetailView.as_view()),
    path("soumissions/<int:id_appel_offre>/open-bids", OpenBidsView.as_view()),
    path("soumissions/<int:soumission_id>/evaluate", EvaluationCreateView.as_view()),
    path("soumissions/<int:soumission_id>/retirer", SoumissionWithdrawView.as_view()),
    path("soumissions/<int:soumission_id>/terminer-evaluation", SoumissionTerminerEvaluationView.as_view()),
    path("soumissions/<int:soumission_id>/conformite", SoumissionConformitePatchView.as_view()),
    path("appels-offres/<int:appel_id>/soumissions", AppelOffreSoumissionsView.as_view()),
    path("api/appels-offres/<int:appel_id>/soumissions", AppelOffreSoumissionsView.as_view()),
    path("operateurs-economiques/<int:operateur_id>/soumissions", OperateurSoumissionsView.as_view()),
    path("api/operateurs-economiques/<int:operateur_id>/soumissions", OperateurSoumissionsView.as_view()),
    path("api/", include("apps.recours.presentation.urls")),
    path("api/soumissions/<int:soumission_id>/documents/", SoumissionDocumentsView.as_view()),
    path("soumissions/<int:soumission_id>/documents", SoumissionDocumentsView.as_view()),
    path("journaux-audit/", include("ledger.urls")),
    path("journaux-audit/", include("readstore.urls")),
    path("journaux-audit/", include("integrity.urls")),
]
