from django.urls import path
from .views import (
    DocumentCollectionView,
    DocumentDetailView,
    DocumentUploadView,
    DocumentDownloadView,
    DocumentDownloadUrlView,
    DocumentBulkZipView,
    DocumentMetadataPatchView,
    DocumentSearchView,
    DocumentDeleteView,
    OperateurDocumentsView,
)

urlpatterns = [
    path('documents', DocumentCollectionView.as_view(), name='document_collection_alias'),
    path('documents/<int:id_document>', DocumentDetailView.as_view(), name='document_detail_alias'),
    path('documents/<int:id_document>/download-url', DocumentDownloadUrlView.as_view(), name='document_download_url_alias'),
    path('api/documents/', DocumentUploadView.as_view(), name='document_upload'),
    path('api/documents/search/', DocumentSearchView.as_view(), name='document_search'),
    path('api/documents/zip/', DocumentBulkZipView.as_view(), name='document_zip_download'),
    path('api/documents/by-operateur/<int:id_operateur>/', OperateurDocumentsView.as_view(), name='document_by_operateur'),
    path('api/documents/<int:id_document>/', DocumentDownloadView.as_view(), name='document_download_single'),
    path('api/documents/<int:id_document>/ia-metadata/', DocumentMetadataPatchView.as_view(), name='document_patch_ia'),
    path('api/documents/<int:id_document>/delete/', DocumentDeleteView.as_view(), name='document_delete'),
]
