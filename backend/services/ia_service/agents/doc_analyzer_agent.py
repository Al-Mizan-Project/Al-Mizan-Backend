"""
DocAnalyzerAgent — Perception Agent.

Responsible for extracting text from document binaries using OCR.
Wraps the existing OCR service functions.
"""

from __future__ import annotations

import logging

from .base import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class DocAnalyzerAgent(BaseAgent):
    """
    Extracts readable text from document binaries.

    Uses a cascade strategy:
      1. Native PDF text extraction (pypdf)
      2. Scanned PDF OCR (pdf2image + tesseract)
      3. Image OCR (tesseract)
    """

    def __init__(self):
        super().__init__("doc_analyzer")

    def process(self, message: AgentMessage) -> AgentMessage:
        logger.info("[%s] received request: %d documents", self.name, len(message.payload.get("documents", [])))
        if message.msg_type != "request":
            return self.reply(message, {"error": f"Unexpected msg_type: {message.msg_type}"})

        documents = message.payload.get("documents", [])
        if not documents:
            logger.warning("[%s] no documents to analyze", self.name)
            return self.reply(message, {"error": "No documents provided", "results": []})

        results = []
        for doc in documents:
            binary = doc.get("binary")
            filename = doc.get("filename", "")
            if binary is None:
                results.append({"id_document": doc.get("id_document"), "text": "", "engine": "none", "used": False, "error": "No binary data"})
                continue

            extraction = self._extract_text(binary, filename)
            results.append({
                "id_document": doc.get("id_document"),
                "text": extraction["text"],
                "engine": extraction["engine"],
                "used": extraction["used"],
            })

        return self.reply(message, {"results": results, "count": len(results)})

    def _extract_text(self, payload: bytes, filename: str) -> dict:
        """Cascade OCR extraction — delegates to the existing ocr service."""
        from ..services.ocr import extract_document_text
        return extract_document_text(payload, filename)
