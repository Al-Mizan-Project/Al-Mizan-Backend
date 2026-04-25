from django.urls import path
from .views import AuditListView, AuditDetailView, AuditByUserView, AuditByEntityView

urlpatterns = [
    path("list/", AuditListView.as_view(), name="audit-list"),
    path("<int:log_id>/", AuditDetailView.as_view(), name="audit-detail"),
    path("user/<int:user_id>/", AuditByUserView.as_view(), name="audit-by-user"),
    path("entity/<str:entite_type>/<int:entite_id>/", AuditByEntityView.as_view(), name="audit-by-entity",),
]