from django.urls import path
from .views import MembreCreateView, MembreRetrieveView

urlpatterns = [
    path("membres", MembreCreateView.as_view()),
    path("membres/<int:membre_id>", MembreRetrieveView.as_view()),
]
