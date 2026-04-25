from django.conf import settings
from django.urls import path

from apps.integrations.appels_client import AppelsClient
from apps.integrations.audit_client import AuditClient
from apps.integrations.notification_client import NotificationClient
from apps.integrations.soumissions_client import SoumissionsClient
from apps.recours.application.services.recours_service import RecoursService
from apps.recours.domain.services.recours_domain_service import RecoursDomainService
from apps.recours.infrastructure.repositories.django_recours_repository import DjangoRecoursRepository
from apps.recours.presentation.views.recours_views import (
    RecoursListCreateView,
    RecoursDetailView,
    RecoursInstruireView,
    RecoursDecisionView,
    RecoursAccepterView,
    RecoursRejeterView,
    RecoursCloturerView,
)


def _build_service():
    timeout = int(getattr(settings, "REMOTE_SERVICE_TIMEOUT", 5))
    return RecoursService(
        repository=DjangoRecoursRepository(),
        domain_service=RecoursDomainService(),
        soumissions_client=SoumissionsClient(settings.SOUMISSIONS_SERVICE_URL, timeout),
        appels_client=AppelsClient(settings.APPELS_SERVICE_URL, timeout),
        notification_client=NotificationClient(settings.NOTIFICATIONS_SERVICE_URL, timeout),
        audit_client=AuditClient(settings.AUDIT_SERVICE_URL, timeout),
    )


recours_service = _build_service()


urlpatterns = [
    path("recours/", RecoursListCreateView.as_view(service=recours_service)),
    path("recours/<int:recours_id>/", RecoursDetailView.as_view(service=recours_service)),
    path("recours/<int:recours_id>/instruire/", RecoursInstruireView.as_view(service=recours_service)),
    path("recours/<int:recours_id>/decision/", RecoursDecisionView.as_view(service=recours_service)),
    path("recours/<int:recours_id>/accepter/", RecoursAccepterView.as_view(service=recours_service)),
    path("recours/<int:recours_id>/rejeter/", RecoursRejeterView.as_view(service=recours_service)),
    path("recours/<int:recours_id>/cloturer/", RecoursCloturerView.as_view(service=recours_service)),
]
