from django.core.management.base import BaseCommand
from documents_service.models import Document
from documents_service.services.minio_client import MinioStorageService
from django.utils import timezone
from datetime import timedelta
import io
import uuid

TEST_OPERATOR_ID = 1

class Command(BaseCommand):
    help = 'Seeds the database and MinIO with sample documents for testing API endpoints'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to seed documents...")
        
        minio_service = MinioStorageService()
        
        samples = [
            {
                "nom": "cahier_des_charges_v1.pdf",
                "related_type": "appel_offre",
                "content": b"Fake Cahier des Charges Content generated for Al-Mizan Appel Offre.",
                "type": "pdf",
                "ia_statut": "VALID",
                "encrypted": False,
                "visible_after": None, # Instantly visible
                "id_operateur_economique": None
            },
            {
                "nom": "offre_financiere_entrepriseA.xlsx",
                "related_type": "soumission",
                "content": b"Fake Financial Offer Data. Highly classified.",
                "type": "xlsx",
                "ia_statut": "PENDING",
                "encrypted": True,
                "visible_after": timezone.now() + timedelta(days=2), # Hidden for 2 days
                "id_operateur_economique": TEST_OPERATOR_ID
            },
            {
                "nom": "offre_technique_entrepriseA.pdf",
                "related_type": "soumission",
                "content": b"Fake Technical specs and architecture proposed by Enterprise A.",
                "type": "pdf",
                "ia_statut": "VALID",
                "encrypted": False,
                "visible_after": timezone.now() - timedelta(days=5), # Visible since 5 days ago
                "id_operateur_economique": TEST_OPERATOR_ID
            },
            {
                "nom": "contrat_final_signe.docx",
                "related_type": "contrat",
                "content": b"Fake Contract Agreement terms and conditions signed by both parties.",
                "type": "docx",
                "ia_statut": "PENDING",
                "encrypted": False,
                "visible_after": None,
                "id_operateur_economique": None
            },
            {
                "nom": "piece_jointe_anomalie.jpg",
                "related_type": "autre",
                "content": b"Fake Image showing an anomaly or scanned ID.",
                "type": "jpg",
                "ia_statut": "ANOMALY",
                "encrypted": False,
                "visible_after": None,
                "id_operateur_economique": TEST_OPERATOR_ID
            }
        ]
        
        for sample in samples:
            obj_name = f"{uuid.uuid4()}.{sample['type']}"
            file_stream = io.BytesIO(sample['content'])
            
            # 1. Upload to MinIO
            self.stdout.write(f"Uploading {sample['nom']} to MinIO...")
            hash_val = minio_service.stream_upload_and_hash(file_stream, obj_name)
            
            # 2. Save to Postgres
            storage_url = f"{minio_service.bucket}/{obj_name}"
            
            doc = Document.objects.create(
                nom=sample['nom'],
                related_type=sample['related_type'],
                type_document=sample['type'],
                storage_url=storage_url,
                hash_sha256=hash_val,
                taille_fichier=len(sample['content']),
                is_encrypted=sample['encrypted'],
                ia_verif_statut=sample['ia_statut'],
                visible_after=sample['visible_after'],
                id_operateur_economique=sample['id_operateur_economique']
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded document ID: {doc.id_document} | {doc.nom}"))
            
        self.stdout.write(self.style.SUCCESS('All sample documents injected into Database & MinIO.'))
