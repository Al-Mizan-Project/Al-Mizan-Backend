"""
DocClassifierAgent — Classification Agent.

Responsible for inferring the canonical document type from document text
and metadata. Uses exact match first, then semantic similarity fallback.
"""

from __future__ import annotations

import logging

from .base import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class DocClassifierAgent(BaseAgent):
    """
    Classifies documents into canonical types:
      - offre_technique
      - offre_financiere
      - declaration_souscrire
      - declaration_probite

    Strategy: exact substring match → semantic embedding similarity.
    """

    def __init__(self):
        super().__init__("doc_classifier")

    def process(self, message: AgentMessage) -> AgentMessage:
        logger.info("[%s] received request: %d documents to classify", self.name, len(message.payload.get("documents", [])))
        if message.msg_type != "request":
            return self.reply(message, {"error": f"Unexpected msg_type: {message.msg_type}"})

        documents = message.payload.get("documents", [])
        if not documents:
            return self.reply(message, {"error": "No documents to classify", "results": []})

        results = []
        for doc in documents:
            doc_type = self._classify(doc)
            results.append({
                "id_document": doc.get("id_document"),
                "type_document": doc_type,
                "nom": doc.get("nom", ""),
            })

        return self.reply(message, {"results": results, "count": len(results)})

    def _classify(self, doc: dict) -> str:
        """Infer the canonical document type from metadata + OCR text."""
        from ..services.conformite import infer_document_type_from_metadata
        return infer_document_type_from_metadata(doc)
