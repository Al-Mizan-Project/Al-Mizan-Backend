# OCR Setup (Local)

This IA service now supports real document text extraction for compliance analysis:

- PDF text extraction: `pypdf`
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

## 3) Optional IA environment variables

- `OCR_TESSERACT_LANG` (default: `fra+ara`)
- `OCR_FALLBACK_IMAGE_ATTEMPT` (default: `true`)

Example:

```env
OCR_TESSERACT_LANG=fra+ara
OCR_FALLBACK_IMAGE_ATTEMPT=true
```

## 4) Trigger automatic compliance endpoint

`POST /ia/conformite/verifier-soumission-auto/<soumission_id>`

Example payload:

```json
{
  "id_appel_offre": 77,
  "provided_document_ids": [101, 102, 103],
  "perform_ocr": true
}
```

## Notes

- If OCR tools are unavailable, the endpoint still works with filename/type NLP inference.
- OCR text is used to improve document type classification, not to block request execution.
