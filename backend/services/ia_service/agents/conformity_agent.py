"""
ConformityAgent — Validation Agent.

Responsible for validating provided documents against required document types.
Produces the conformity status (CONFORME, PIECES_MANQUANTES, NON_CONFORME)
and a detailed report.
"""

from __future__ import annotations

import logging

from .base import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class ConformityAgent(BaseAgent):
    """
    Validates document conformity.

    Checks:
      - Missing documents (required types not provided)
      - Invalid documents (provided but flagged as invalid)
      - Duplicate documents (same type provided multiple times)
    """

    def __init__(self):
        super().__init__("conformity")

    def process(self, message: AgentMessage) -> AgentMessage:
        required = message.payload.get("required_documents", [])
        provided = message.payload.get("provided_documents", [])
        logger.info("[%s] received request: %d required, %d provided", self.name, len(required), len(provided))
        if message.msg_type != "request":
            return self.reply(message, {"error": f"Unexpected msg_type: {message.msg_type}"})

        status, report = self._check(required, provided)

        return self.reply(message, {
            "conformite_statut": status,
            "conformite_rapport": report,
        })

    def _check(self, required_documents: list[str], provided_documents: list[dict]) -> tuple[str, dict]:
        """Delegate to the existing conformity check logic."""
        from ..services.conformite import run_conformite_check
        return run_conformite_check(required_documents, provided_documents)
