from django.urls import path
from .views import (
    DocumentUploadView,
    DocumentDownloadView,
    DocumentBulkZipView,
    DocumentMetadataPatchView,
    DocumentSearchView,
    DocumentDeleteView
)

urlpatterns = [
    path('api/documents/', DocumentUploadView.as_view(), name='document_upload'),
    path('api/documents/search/', DocumentSearchView.as_view(), name='document_search'),
    path('api/documents/zip/', DocumentBulkZipView.as_view(), name='document_zip_download'),
    path('api/documents/<int:id_document>/', DocumentDownloadView.as_view(), name='document_download_single'),
    path('api/documents/<int:id_document>/ia-metadata/', DocumentMetadataPatchView.as_view(), name='document_patch_ia'),
    path('api/documents/<int:id_document>/delete/', DocumentDeleteView.as_view(), name='document_delete'),
]
