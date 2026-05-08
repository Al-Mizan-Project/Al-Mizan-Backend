from django.urls import path

from .views import (
    EvaluationCreateView,
    OpenBidsView,
    SoumissionConformitePatchView,
    SoumissionCreateView,
    SoumissionDetailView,
    SoumissionDocumentsView,
    SoumissionTerminerEvaluationView,
    SoumissionWithdrawView,
    SoumissionAffecterView,          # <-- added
)

urlpatterns = [
    path('', SoumissionCreateView.as_view(), name='soumission-create'),
    path('<int:soumission_id>/', SoumissionDetailView.as_view(), name='soumission-detail'),
    path('<int:soumission_id>/documents/', SoumissionDocumentsView.as_view(), name='soumission-documents'),
    path('<int:id_appel_offre>/open-bids/', OpenBidsView.as_view(), name='soumission-open-bids'),
    path('<int:soumission_id>/evaluate/', EvaluationCreateView.as_view(), name='soumission-evaluate'),
    path('<int:soumission_id>/retirer/', SoumissionWithdrawView.as_view(), name='soumission-withdraw'),
    path('<int:soumission_id>/terminer-evaluation/', SoumissionTerminerEvaluationView.as_view(), name='soumission-terminer-evaluation'),
    path('<int:soumission_id>/conformite/', SoumissionConformitePatchView.as_view(), name='soumission-conformite-patch'),
    path('<int:soumission_id>/affecter/', SoumissionAffecterView.as_view(), name='soumission-affecter'),   # <-- added
]
