import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default limits (overridable via Django settings)
# ---------------------------------------------------------------------------
DEFAULT_MAX_OCR_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
DEFAULT_OCR_MAX_WORKERS = 4


def _get_max_file_size() -> int:
    return int(getattr(settings, "MAX_OCR_FILE_SIZE", DEFAULT_MAX_OCR_FILE_SIZE))


def _get_max_workers() -> int:
    return int(getattr(settings, "OCR_MAX_WORKERS", DEFAULT_OCR_MAX_WORKERS))


# ---------------------------------------------------------------------------
# Extraction engines
# ---------------------------------------------------------------------------
def _extract_pdf_text(payload: bytes) -> str:
    """Extract embedded text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except Exception:
        logger.debug("pypdf is not available for PDF extraction")
        return ""

    text_parts = []
    try:
        reader = PdfReader(io.BytesIO(payload))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
    except Exception as exc:
        logger.debug("PDF extraction failed: %s", exc)
        return ""
    return "\n".join(text_parts).strip()


def _extract_pdf_ocr_text(payload: bytes) -> str:
    """
    Convert each page of a scanned PDF to an image and run Tesseract OCR.

    Requires ``pdf2image`` (which depends on the poppler command-line tools).
    Falls back silently when the library or poppler is not installed.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except Exception:
        logger.debug("pdf2image/pytesseract is not available for PDF-OCR")
        return ""

    ocr_lang = getattr(settings, "OCR_TESSERACT_LANG", "fra+ara")
    text_parts: list[str] = []
    try:
        images = convert_from_bytes(payload, dpi=200)
        for image in images:
            page_text = (pytesseract.image_to_string(image, lang=ocr_lang) or "").strip()
            if page_text:
                text_parts.append(page_text)
    except Exception as exc:
        logger.debug("PDF-OCR extraction failed: %s", exc)
        return ""
    return "\n".join(text_parts).strip()


def _extract_image_ocr_text(payload: bytes) -> str:
    """Run Tesseract OCR on a raster image (PNG, JPG, TIFF, BMP …)."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        logger.debug("pytesseract/Pillow is not available for OCR")
        return ""

    try:
        image = Image.open(io.BytesIO(payload))
        ocr_lang = getattr(settings, "OCR_TESSERACT_LANG", "fra+ara")
        return (pytesseract.image_to_string(image, lang=ocr_lang) or "").strip()
    except Exception as exc:
        logger.debug("Image OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Main entry point — single document
# ---------------------------------------------------------------------------
def extract_document_text(payload: bytes, filename: str = "") -> Dict:
    """
    Extract readable text from a document binary.

    Strategy (cascade):
    1. If the file is a PDF → try native text extraction (pypdf).
    2. If pypdf returned nothing → try PDF-OCR (pdf2image + tesseract).
    3. If the file is a raster image → try image OCR (tesseract).
    4. Fallback: attempt image OCR for unknown extensions if enabled.

    Returns ``{"text": ..., "engine": ..., "used": bool}``.
    """
    if not payload:
        return {"text": "", "engine": "none", "used": False}

    # ── Size guard ──────────────────────────────────────────────────────
    max_size = _get_max_file_size()
    if len(payload) > max_size:
        logger.info(
            "Skipping OCR for %s: file size %d bytes exceeds MAX_OCR_FILE_SIZE (%d bytes)",
            filename or "<unknown>",
            len(payload),
            max_size,
        )
        return {
            "text": "",
            "engine": "none",
            "used": False,
            "skipped_reason": "file_too_large",
        }

    lowered = (filename or "").lower()
    extracted = ""
    engine = "none"

    # ── PDF pipeline ────────────────────────────────────────────────────
    if lowered.endswith(".pdf"):
        extracted = _extract_pdf_text(payload)
        engine = "pypdf" if extracted else "none"

        # Scanned-PDF fallback: convert pages to images then OCR
        if not extracted:
            extracted = _extract_pdf_ocr_text(payload)
            engine = "pdf2image+tesseract" if extracted else "none"

    # ── Raster image pipeline ───────────────────────────────────────────
    if not extracted and lowered.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
        extracted = _extract_image_ocr_text(payload)
        engine = "tesseract" if extracted else "none"

    # ── Fallback for unknown extensions ─────────────────────────────────
    if not extracted and getattr(settings, "OCR_FALLBACK_IMAGE_ATTEMPT", True):
        fallback = _extract_image_ocr_text(payload)
        if fallback:
            extracted = fallback
            engine = "tesseract"

    return {
        "text": extracted,
        "engine": engine,
        "used": bool(extracted),
    }


# ---------------------------------------------------------------------------
# Parallel OCR helper — multi-document
# ---------------------------------------------------------------------------
def extract_documents_text_parallel(
    items: List[Tuple[bytes, str]],
) -> List[Dict]:
    """
    Run :func:`extract_document_text` on multiple ``(payload, filename)``
    pairs **in parallel** using a thread pool.

    Thread-based parallelism is appropriate here because the heavy work
    happens inside C extensions (pypdf, Pillow, Tesseract) which release
    the GIL.

    Returns results **in the same order** as *items*.
    """
    max_workers = min(_get_max_workers(), len(items)) if items else 1

    if max_workers <= 1 or len(items) <= 1:
        return [extract_document_text(payload, filename) for payload, filename in items]

    results: List[Dict] = [{}] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(extract_document_text, payload, filename): idx
            for idx, (payload, filename) in enumerate(items)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.warning("Parallel OCR failed for item %d: %s", idx, exc)
                results[idx] = {"text": "", "engine": "none", "used": False}
    return results
