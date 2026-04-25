from django.urls import path
from .views import VerifyFullChainView, VerifyRecordView

urlpatterns = [
    path('verifier-integrite/', VerifyFullChainView.as_view(), name='verify-full-chain'),
    path("verifier-integrite/record/<int:record_id>/", VerifyRecordView.as_view(), name="verify-record"),
]