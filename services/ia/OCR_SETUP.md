# OCR Setup (Local)

This IA service now supports real document text extraction for compliance analysis:

- PDF text extraction: `pypdf`
- Scanned PDF OCR: `pdf2image` + `pytesseract` (requires **poppler**)
- Image OCR: `pytesseract` + local `tesseract-ocr` binary

## 1) Install Python dependencies

```bash
pip install -r requirements.txt
```

## 2) Install Tesseract engine (Windows)

1. Install Tesseract OCR locally (for example from UB Mannheim builds).
2. Add the installation directory to your `PATH`.
3. Verify:

```bash
tesseract --version
```

## 3) Install Poppler (required for scanned PDF → image conversion)

### Windows
1. Download poppler for Windows from [GitHub releases](https://github.com/osmart/poppler-windows/releases).
2. Extract and add the `bin/` directory to your `PATH`.
3. Verify:

```bash
pdfinfo --version
```

### Linux (Debian/Ubuntu)
```bash
sudo apt-get install poppler-utils
```

### Docker
The Dockerfile should include:
```dockerfile
RUN apt-get update && apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara
```

## 4) Optional IA environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_TESSERACT_LANG` | `fra+ara` | Languages for Tesseract OCR |
| `OCR_FALLBACK_IMAGE_ATTEMPT` | `true` | Try image OCR on files with unknown extensions |
| `MAX_OCR_FILE_SIZE` | `20971520` (20 MB) | Max file size in bytes for OCR processing |
| `OCR_MAX_WORKERS` | `4` | Max parallel threads for batch OCR |

Example `.env`:

```env
OCR_TESSERACT_LANG=fra+ara
OCR_FALLBACK_IMAGE_ATTEMPT=true
MAX_OCR_FILE_SIZE=20971520
OCR_MAX_WORKERS=4
```

## 5) Trigger automatic compliance endpoint

`POST /ia/conformite/verifier-soumission-auto/<soumission_id>`

Example payload:

```json
{
  "id_appel_offre": 77,
  "provided_document_ids": [101, 102, 103],
  "perform_ocr": true
}
```

## OCR Processing Pipeline

```
Document binary
  │
  ├── Extension .pdf?
  │     ├── pypdf (native text) ──→ ✅ text found → engine: "pypdf"
  │     └── empty? → pdf2image + tesseract ──→ ✅ text found → engine: "pdf2image+tesseract"
  │
  ├── Extension .png/.jpg/.tif/.bmp?
  │     └── pytesseract (image OCR) ──→ ✅ text found → engine: "tesseract"
  │
  └── Unknown extension? (fallback enabled)
        └── pytesseract (image OCR) ──→ ✅ text found → engine: "tesseract"
```

## Notes

- If OCR tools are unavailable, the endpoint still works with filename/type NLP inference.
- OCR text is used to improve document type classification, not to block request execution.
- Files exceeding `MAX_OCR_FILE_SIZE` are skipped with a `skipped_reason: "file_too_large"` indicator.
- Multi-document OCR is processed in parallel (up to `OCR_MAX_WORKERS` threads) for performance.
- Thread-based parallelism is used because Tesseract/pypdf release the GIL during C-extension calls.
