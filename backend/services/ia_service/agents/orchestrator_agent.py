"""
OrchestratorAgent — Coordination Agent.

Manages the multi-agent conformity analysis workflow:
  1. Receives the initial verification request
  2. Delegates document analysis to DocAnalyzerAgent
  3. Delegates document classification to DocClassifierAgent
  4. Delegates conformity validation to ConformityAgent
  5. Aggregates results and returns the final response

Each delegation happens via AgentMessage passing.
"""

from __future__ import annotations

import logging

from .base import AgentMessage, BaseAgent
from .doc_analyzer_agent import DocAnalyzerAgent
from .doc_classifier_agent import DocClassifierAgent
from .conformity_agent import ConformityAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Coordinates the multi-agent conformity analysis.

    Collaborates with:
      - DocAnalyzerAgent  (perception / OCR)
      - DocClassifierAgent (classification)
      - ConformityAgent    (validation decision)
    """

    def __init__(self):
        super().__init__("orchestrator")
        self.doc_analyzer = DocAnalyzerAgent()
        self.doc_classifier = DocClassifierAgent()
        self.conformity = ConformityAgent()

    def process(self, message: AgentMessage) -> AgentMessage:
        if message.msg_type != "request":
            return self.reply(message, {"error": f"Unexpected msg_type: {message.msg_type}"})

        required_documents = message.payload.get("required_documents", [])
        provided_documents_meta = message.payload.get("provided_documents_meta", [])
        provided_documents_binaries = message.payload.get("provided_documents_binaries", [])
        perform_ocr = message.payload.get("perform_ocr", True)

        # ── Step 1: Document Analysis (OCR) ──────────────────────────
        analyzer_result = self._call_agent(
            self.doc_analyzer,
            "analyze_documents",
            {"documents": provided_documents_binaries},
        )
        ocr_results = analyzer_result.payload.get("results", [])

        # Enrich metadata with OCR text
        ocr_by_id = {r["id_document"]: r for r in ocr_results if r.get("used")}
        enriched_meta = []
        for doc in provided_documents_meta:
            doc_id = doc.get("id_document")
            ocr = ocr_by_id.get(doc_id, {})
            enriched_doc = dict(doc)
            if ocr.get("text"):
                enriched_doc["ocr_text"] = ocr["text"]
            enriched_meta.append(enriched_doc)

        # ── Step 2: Document Classification ───────────────────────────
        classifier_result = self._call_agent(
            self.doc_classifier,
            "classify_documents",
            {"documents": enriched_meta},
        )
        classified = classifier_result.payload.get("results", [])

        # ── Step 3: Conformity Validation ────────────────────────────
        provided_for_check = []
        for item in classified:
            doc_type = item.get("type_document", "")
            if doc_type:
                provided_for_check.append({
                    "id_document": item.get("id_document"),
                    "type_document": doc_type,
                    "is_valid": True,
                })

        conformity_result = self._call_agent(
            self.conformity,
            "validate_conformity",
            {
                "required_documents": required_documents,
                "provided_documents": provided_for_check,
            },
        )

        report = conformity_result.payload.get("conformite_rapport", {})
        status = conformity_result.payload.get("conformite_statut", "ERROR")

        # ── Aggregate final response ─────────────────────────────────
        ocr_processed = sum(1 for r in ocr_results if r.get("used") is not None)
        ocr_succeeded = sum(1 for r in ocr_results if r.get("used"))

        return self.reply(message, {
            "conformite_statut": status,
            "conformite_rapport": report,
            "analysis_context": {
                "required_documents": required_documents,
                "classified_documents": classified,
                "ocr": {
                    "enabled": perform_ocr,
                    "processed": ocr_processed,
                    "succeeded": ocr_succeeded,
                },
            },
        })

    def _call_agent(self, agent: BaseAgent, action: str, payload: dict) -> AgentMessage:
        """Send a message to a sub-agent and return its response."""
        request = AgentMessage(
            sender=self.name,
            recipient=agent.name,
            msg_type="request",
            payload=payload,
            context={"action": action},
        )
        logger.info("[%s] → sending request to %s (action=%s)", self.name, agent.name, action)
        response = agent.process(request)
        logger.info("[%s] ← received response from %s", self.name, agent.name)
        return response
