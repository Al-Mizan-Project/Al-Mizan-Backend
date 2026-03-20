import io
import logging
from typing import Dict

from django.conf import settings

logger = logging.getLogger(__name__)


def _extract_pdf_text(payload: bytes) -> str:
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


def _extract_image_ocr_text(payload: bytes) -> str:
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


def extract_document_text(payload: bytes, filename: str = "") -> Dict:
    if not payload:
        return {"text": "", "engine": "none", "used": False}

    lowered = (filename or "").lower()
    extracted = ""
    engine = "none"

    if lowered.endswith(".pdf"):
        extracted = _extract_pdf_text(payload)
        engine = "pypdf" if extracted else "none"

    if not extracted and lowered.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
        extracted = _extract_image_ocr_text(payload)
        engine = "tesseract" if extracted else "none"

    # Fallback for unknown extensions when OCR is explicitly enabled.
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
