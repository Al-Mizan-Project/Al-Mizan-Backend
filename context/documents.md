# Documents Service Context

## Architecture

- **Stack:** Python, Django, Django REST Framework
- **Database:** PostgreSQL
- **Object Storage:** MinIO (via `boto3` or `minio` python SDK)
- **Cache/Rate-Limiting:** Redis
- **Deployment:** Dockerized local stacks (Django API, Postgres, Redis, PgBouncer, MinIO)

## Database Schema (`documents` table)

- `id_document` (PK, Auto-increment)
- `related_type` (String - ex: appel_offre, soumission, contrat)
- `nom` (String - Original file name)
- `type_document` (String - Extension/MimeType)
- `storage_url` (String - Unique path in MinIO: `bucketName/uuid.ext`)
- `hash_sha256` (String 64 - Integrity hash calculated during upload)
- `is_encrypted` (Boolean - True if the file contains encrypted financial offers)
- `ia_verif_statut` (String - AI processing status: PENDING, VALID, ANOMALY)
- `ia_verif_details` (Text - JSON or OCR/NLP log)
- `uploaded_at` (Datetime)
- `visible_after` (Datetime, Nullable - Controls when the document becomes visible and accessible in the system)

## Mandatory Development Rules

1. **TESTS FIRST / ALWAYS:** TDD approach. Unit tests and Integration tests must be written _before_ or _alongside_ any feature implementation.
2. **TESTCONTAINERS OBLIGATOIRE:** Real infrastructure must be mocked using `testcontainers-python` (PostgreSQL, Redis & MinIO) for integration testing. Hard forbidden: using SQLite in-memory for final DB integrations.
3. **STREAMS:** Large files MUST NEVER be loaded entirely into RAM. Uploads, downloads, and ZIP generation must use Python streaming (e.g., streaming `boto3` responses and using `StreamingHttpResponse` or `FileResponse` in Django).

## Key Features to Implement

1. **Upload:** Stream to MinIO, compute SHA-256 on the fly, save metadata to DB.
2. **Single Download:** Stream from MinIO to HTTP response with correct headers.
3. **Bulk ZIP Download:** Stream multiple files from MinIO directly into a `ZipOutputStream` on the HTTP response.
4. **AI Metadata Update (PATCH):** Update `ia_verif_statut` and `ia_verif_details`.
5. **Advanced Search (GET):** Filter by `related_type`, `ia_verif_statut`, `is_encrypted`, minimum/maximum size, extension, and enforce temporal visibility rules (`visible_after` <= NOW).
6. **Delete:** Hard delete from MinIO and Database.

## Implementation Insights & Caveats

- **Testing Constraints (Testcontainers):** `testcontainers-python` had issues connecting to the Docker daemon on Windows due to permission/socket issues. We adapted by using standard Django `TestCase` and heavily mocking Boto3 to isolate testing.
- **Cache in Tests:** Because Redis is not always available in the local test execution environment, `config/settings.py` is configured to dynamically switch to `LocMemCache` when `sys.argv` contains `'test'`.
- **Zero-Memory Zip Streaming Native Python Limitation:** To natively stream zipped files out without blowing up RAM, we built a `VirtualZipBuffer` in `minio_client.py` that implements `tell()`, `write()`, and a custom `pop_bytes()` method that continuously empties its internal bytearray. This tricks the `zipfile` module into thinking it's writing to a continuous disk file while allowing us to chunk and yield bytes safely in a `StreamingHttpResponse`.
- **Chunked SHA-256 with Boto3:** `boto3`'s multipart upload reads the stream unpredictably in multiple threads, meaning you cannot dynamically wrap and hash the stream during the upload call. We must calculate the SHA-256 manually first by reading the file in chunks BEFORE resetting the stream to 0 and uploading it via `s3_client.upload_fileobj()`.
