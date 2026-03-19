from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from ia_service.views import HealthView, ReadyView

urlpatterns = [
    path("health", HealthView.as_view()),
    path("ready", ReadyView.as_view()),
    path("openapi.json", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("", include("ia_service.urls")),
]