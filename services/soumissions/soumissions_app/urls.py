from django.urls import path
from .views import SoumissionCreateView, OpenBidsView, EvaluationCreateView

urlpatterns = [
    path('', SoumissionCreateView.as_view(), name='soumission-create'),
    path('<int:id_appel_offre>/open-bids/', OpenBidsView.as_view(), name='soumission-open-bids'),
    path('<int:soumission_id>/evaluate/', EvaluationCreateView.as_view(), name='soumission-evaluate'),
]
