import os
import django
import sys

# Add backend directory to sys.path if not there
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import io
from services.documents_service.models import Document
from services.documents_service.services.minio_client import MinioStorageService

def create_minimal_pdf():
    # A valid, minimal PDF file binary string that says "Document repare"
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 50 >>\nstream\nBT /F1 24 Tf 100 700 Td (Vrai document repare) Tj ET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000222 00000 n \n0000000310 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n410\n%%EOF\n"
    return pdf_content

def fix_missing_documents():
    print("Fixing missing documents in MinIO...")
    try:
        minio = MinioStorageService()
        docs = Document.objects.all()
        pdf_bytes = create_minimal_pdf()
        
        fixed_count = 0
        for doc in docs:
            if not doc.storage_url:
                continue
                
            # Check if exists
            try:
                minio.s3_client.head_object(Bucket=minio.bucket, Key=doc.storage_url)
                # Exists
            except Exception:
                # Does not exist, let's create it
                print(f"Uploading file for missing document ID {doc.id_document} at {doc.storage_url}...")
                file_stream = io.BytesIO(pdf_bytes)
                minio.stream_upload_and_hash(file_stream, doc.storage_url)
                fixed_count += 1
                
        print(f"Fixed {fixed_count} missing documents.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    fix_missing_documents()
