from django.core.management.base import BaseCommand
from documents_service.models import Document
from documents_service.services.minio_client import MinioStorageService
from django.utils import timezone
from datetime import timedelta
import io
import uuid

TEST_OPERATOR_ID = 1


def _escape_pdf_text(value):
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(title):
    text = _escape_pdf_text(title)
    stream = f"BT /F1 12 Tf 36 108 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 320 160] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    body = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

    xref_position = len(body)
    body += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    body += b"0000000000 65535 f \n"
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode("ascii")
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode("ascii")
    return body

class Command(BaseCommand):
    help = 'Seeds the database and MinIO with sample documents for testing API endpoints'

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing document metadata before seeding")
        parser.add_argument(
            "--operator-id",
            type=int,
            default=TEST_OPERATOR_ID,
            help="Operator id assigned to seeded soumission documents",
        )

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to seed documents...")

        if kwargs["flush"]:
            deleted, _ = Document.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing document rows."))

        operator_id = kwargs["operator_id"]
        
        minio_service = MinioStorageService()
        
        samples = [
            {
                "nom": "cahier_des_charges_v1.pdf",
                "related_type": "appel_offre",
                "content": _pdf_bytes("Al-Mizan cahier des charges"),
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
                "id_operateur_economique": operator_id
            },
            {
                "nom": "offre_technique_entrepriseA.pdf",
                "related_type": "soumission",
                "content": _pdf_bytes("Al-Mizan accuse de reception"),
                "type": "pdf",
                "ia_statut": "VALID",
                "encrypted": False,
                "visible_after": timezone.now() - timedelta(days=5), # Visible since 5 days ago
                "id_operateur_economique": operator_id
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
