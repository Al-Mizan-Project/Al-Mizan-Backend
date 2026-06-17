import sqlite3
import boto3
import io

def create_minimal_pdf():
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 50 >>\nstream\nBT /F1 24 Tf 100 700 Td (Vrai document repare) Tj ET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000222 00000 n \n0000000310 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n410\n%%EOF\n"
    return pdf_content

def fix_documents():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT id_document, storage_url FROM documents_document")
    rows = cursor.fetchall()

    s3_client = boto3.client(
        's3',
        endpoint_url='http://127.0.0.1:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
        region_name='us-east-1'
    )
    bucket = 'al-mizan-documents'

    try:
        s3_client.head_bucket(Bucket=bucket)
    except:
        s3_client.create_bucket(Bucket=bucket)

    pdf_bytes = create_minimal_pdf()
    fixed_count = 0

    for doc_id, storage_url in rows:
        if not storage_url:
            continue
        try:
            s3_client.head_object(Bucket=bucket, Key=storage_url)
        except Exception:
            # File missing, upload dummy
            print(f"Uploading dummy PDF for Document ID {doc_id} to {storage_url}")
            file_stream = io.BytesIO(pdf_bytes)
            s3_client.upload_fileobj(file_stream, bucket, storage_url)
            fixed_count += 1

    print(f"Successfully fixed {fixed_count} missing documents in MinIO.")

if __name__ == '__main__':
    fix_documents()
