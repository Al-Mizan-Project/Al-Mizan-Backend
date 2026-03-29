from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny
from auth_service.views import HealthView, ReadyView

urlpatterns = [
    path("health", HealthView.as_view()),
    path("ready", ReadyView.as_view()),
    path("openapi.json", SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]), name="openapi-schema"),
    path("", include("auth_service.urls")),
]
