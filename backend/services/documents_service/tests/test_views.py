import io
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from documents_service.models import Document

class DocumentApiTests(APITestCase):

    def setUp(self):
        # We need a user to bypass IsAuthenticated
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

    @patch('documents_service.views.MinioStorageService.stream_upload_and_hash')
    def test_upload_document(self, mock_stream_upload):
        # Arrange
        mock_stream_upload.return_value = "fake-sha-256-hash-value"
        url = reverse('document_upload')
        
        file_content = b"Fake PDF Data"
        file_obj = io.BytesIO(file_content)
        file_obj.name = 'test_document.pdf'
        
        data = {
            'file': file_obj,
            'related_type': 'appel_offre',
            'is_encrypted': 'False'
        }

        # Act
        response = self.client.post(url, data, format='multipart')

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Document.objects.count(), 1)
        doc = Document.objects.first()
        self.assertEqual(doc.nom, 'test_document.pdf')
        self.assertEqual(doc.ia_verif_statut, 'PENDING')
        mock_stream_upload.assert_called_once()

    @patch('documents_service.views.MinioStorageService.get_file_stream')
    def test_download_document(self, mock_get_stream):
        # Arrange
        doc = Document.objects.create(
            related_type="soumission",
            nom="offer.pdf",
            type_document="pdf",
            storage_url="almizan-documents/uuid-999.pdf",
            hash_sha256="hash123",
        )
        url = reverse('document_download_single', kwargs={'id_document': doc.id_document})
        
        def fake_stream(*args, **kwargs):
            yield b"Chunk 1"
            yield b"Chunk 2"
            
        mock_get_stream.return_value = fake_stream()

        # Act
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Disposition'), 'attachment; filename="offer.pdf"')
        content = b"".join(response.streaming_content)
        self.assertEqual(content, b"Chunk 1Chunk 2")

    def test_download_url_alias_returns_download_endpoint(self):
        doc = Document.objects.create(
            related_type="appel_offre",
            nom="cdc.pdf",
            type_document="pdf",
            storage_url="almizan-documents/uuid-cdc.pdf",
            hash_sha256="hash-cdc",
        )
        url = reverse('document_download_url_alias', kwargs={'id_document': doc.id_document})

        response = self.client.get(url, HTTP_HOST='10.0.2.2:8000')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id_document"], doc.id_document)
        self.assertEqual(response.data["storage_url"], doc.storage_url)
        self.assertEqual(
            response.data["download_url"],
            f"http://10.0.2.2:8000/api/documents/{doc.id_document}/",
        )

    @patch('documents_service.views.MinioStorageService.stream_zip_downloads')
    def test_download_bulk_zip(self, mock_zip_stream):
        # Arrange
        doc1 = Document.objects.create(
            related_type="soumission",
            nom="offer1.pdf",
            type_document="pdf",
            storage_url="almizan-documents/111.pdf",
            hash_sha256="hash111",
        )
        doc2 = Document.objects.create(
            related_type="soumission",
            nom="offer2.pdf",
            type_document="pdf",
            storage_url="almizan-documents/222.pdf",
            hash_sha256="hash222",
        )
        url = reverse('document_zip_download')
        
        def fake_stream(*args, **kwargs):
            yield b"FakeZipData"
            
        mock_zip_stream.return_value = fake_stream()

        # Act
        response = self.client.get(url, {'ids': f'{doc1.id_document},{doc2.id_document}'})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/zip')
        content = b"".join(response.streaming_content)
        self.assertEqual(content, b"FakeZipData")

    def test_patch_metadata(self):
        doc = Document.objects.create(
            related_type="contrat",
            nom="contract.docx",
            type_document="docx",
            storage_url="uuid-000",
            hash_sha256="abc",
            ia_verif_statut="PENDING"
        )
        url = reverse('document_patch_ia', kwargs={'id_document': doc.id_document})
        
        data = {
            "ia_verif_statut": "VALID",
            "ia_verif_details": '{"confidence": 0.99}'
        }

        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.ia_verif_statut, "VALID")
        self.assertEqual(doc.ia_verif_details, '{"confidence": 0.99}')

    def test_search_documents_with_filters(self):
        Document.objects.create(
            related_type="contrat",
            nom="contract.pdf",
            type_document="pdf",
            storage_url="uuid-1",
            hash_sha256="h1",
            taille_fichier=1500,
        )
        Document.objects.create(
            related_type="soumission",
            nom="offer.docx",
            type_document="docx",
            storage_url="uuid-2",
            hash_sha256="h2",
            taille_fichier=5000,
        )
        
        url = reverse('document_search')
        
        # Test minimum size filter
        response = self.client.get(url, {'min_size': '2000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['type_document'], 'docx')
        
        # Test type filter
        response = self.client.get(url, {'type_document': 'pdf'})
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['related_type'], 'contrat')

    def test_search_documents_with_ids_filter(self):
        doc1 = Document.objects.create(
            related_type="contrat",
            nom="contract.pdf",
            type_document="pdf",
            storage_url="uuid-ids-1",
            hash_sha256="hids1",
        )
        doc2 = Document.objects.create(
            related_type="soumission",
            nom="offer.docx",
            type_document="docx",
            storage_url="uuid-ids-2",
            hash_sha256="hids2",
        )

        url = reverse('document_search')
        response = self.client.get(url, {'ids': f'{doc2.id_document},{doc1.id_document}'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 2)
        self.assertEqual({item['id_document'] for item in results}, {doc1.id_document, doc2.id_document})

    def test_temporal_visibility(self):
        past_date = timezone.now() - timedelta(days=1)
        future_date = timezone.now() + timedelta(days=1)
        
        visible_doc = Document.objects.create(
            related_type="soumission",
            nom="visible.pdf",
            type_document="pdf",
            storage_url="uuid-visible",
            hash_sha256="hash-visible",
            visible_after=past_date
        )
        
        hidden_doc = Document.objects.create(
            related_type="soumission",
            nom="hidden.pdf",
            type_document="pdf",
            storage_url="uuid-hidden",
            hash_sha256="hash-hidden",
            visible_after=future_date
        )
        
        # Test Search (should only return visible doc)
        search_url = reverse('document_search')
        response = self.client.get(search_url)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id_document'], visible_doc.id_document)
        
        # Test direct download of hidden doc (should be forbidden)
        download_url = reverse('document_download_single', kwargs={'id_document': hidden_doc.id_document})
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

