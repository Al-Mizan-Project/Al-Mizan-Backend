from django.urls import path

from .views import (
    EvaluationCreateView,
    OpenBidsView,
    SoumissionConformitePatchView,
    SoumissionCreateView,
)

urlpatterns = [
    path('', SoumissionCreateView.as_view(), name='soumission-create'),
    path('<int:id_appel_offre>/open-bids/', OpenBidsView.as_view(), name='soumission-open-bids'),
    path('<int:soumission_id>/evaluate/', EvaluationCreateView.as_view(), name='soumission-evaluate'),
    path('<int:soumission_id>/conformite/', SoumissionConformitePatchView.as_view(), name='soumission-conformite-patch'),
]
