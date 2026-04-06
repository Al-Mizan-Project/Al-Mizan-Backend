from django.test import TestCase
from documents_service.models import Document

class DocumentModelTest(TestCase):
    def test_document_creation(self):
        doc = Document.objects.create(
            related_type="appel_offre",
            nom="cahier_des_charges.pdf",
            type_document="pdf",
            storage_url="almizan-documents/uuid-1234.pdf",
            hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            is_encrypted=False,
        )
        self.assertEqual(doc.ia_verif_statut, 'PENDING')
        self.assertIsNotNone(doc.uploaded_at)
        self.assertEqual(str(doc), "cahier_des_charges.pdf (appel_offre)")
        self.assertEqual(Document.objects.count(), 1)
