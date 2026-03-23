from django.urls import path
from .views.recours_views import *

urlpatterns = [
    path("recours/", RecoursCreateView.as_view()),
    path("recours/list/", RecoursListView.as_view()),
    path("recours/<int:recours_id>/", RecoursDetailView.as_view()),

    path("recours/<int:recours_id>/instruire/", RecoursInstruireView.as_view()),
    path("recours/<int:recours_id>/decision/", RecoursDecisionView.as_view()),
    path("recours/<int:recours_id>/accepter/", RecoursAccepterView.as_view()),
    path("recours/<int:recours_id>/rejeter/", RecoursRejeterView.as_view()),
    path("recours/<int:recours_id>/cloturer/", RecoursCloturerView.as_view()),
]