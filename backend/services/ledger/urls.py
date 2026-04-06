from django.urls import path
from .views import CreateAuditLogView

urlpatterns = [
    path('create/', CreateAuditLogView.as_view(), name='create_audit_log'),
]