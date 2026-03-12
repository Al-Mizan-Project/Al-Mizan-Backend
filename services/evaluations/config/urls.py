from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView
from evaluations_service.views import HealthView, ReadyView

urlpatterns = [
    path("health", HealthView.as_view()),
    path("ready", ReadyView.as_view()),
    path("openapi.json", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("", include("evaluations_service.urls")),
]
