from django.urls import path
from .views import (
    EvaluationView,
    EvaluationDetailView,
    SoumissionEvaluationsView,
    AppelOffreEvaluationsView,
    CalculerClassementView,
    ClassementView,
    ValiderNotesView
)

urlpatterns = [
    path('evaluations', EvaluationView.as_view(), name='evaluations'),
    path('evaluations/<int:evaluation_id>', EvaluationDetailView.as_view(), name='evaluation_detail'),
    path('soumissions/<int:soumission_id>/evaluations', SoumissionEvaluationsView.as_view(), name='soumission_evaluations'),
    path('appels-offres/<int:appel_id>/evaluations', AppelOffreEvaluationsView.as_view(), name='appel_offre_evaluations'),
    path('appels-offres/<int:appel_id>/calculer-classement', CalculerClassementView.as_view(), name='calculer_classement'),
    path('appels-offres/<int:appel_id>/classement', ClassementView.as_view(), name='classement'),
    path('appels-offres/<int:appel_id>/valider-notes', ValiderNotesView.as_view(), name='valider_notes'),
]
