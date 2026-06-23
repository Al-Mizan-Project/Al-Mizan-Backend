from typing import List

from ..anomalies import _detect_hors_delai
from .base_agent import BaseAgent
from .message_bus import Message, MessageType


class DeadlineAgent(BaseAgent):
    """
    Agent spécialisé dans la vérification des délais de soumission.
    Détecte :
    - Soumission déposée après la date limite (hors délai)
    """

    def __init__(self):
        super().__init__(
            name="AgentDelai",
            role="Vérification du respect des délais de soumission",
        )

    def handle_message(self, message: Message) -> List[Message]:
        responses = []

        if message.type == MessageType.ANALYSE_DELAI:
            payload = message.payload
            soumission = payload.get("soumission", {})
            appel = payload.get("appel", {})

            anomalies = []
            rules_applied = []

            r = _detect_hors_delai(soumission, appel)
            if r:
                anomalies.append(r)
                rules_applied.append("hors_delai")

            date_soumission = soumission.get("date_soumission", "N/A")
            date_limite = appel.get("date_limite_soumission", "N/A")

            responses.append(message.reply(
                MessageType.RESULTAT_ANOMALIE,
                {
                    "agent": self.name,
                    "anomalies": anomalies,
                    "rules_applied": rules_applied,
                    "nb_anomalies": len(anomalies),
                    "analyse_detail": {
                        "date_soumission": str(date_soumission),
                        "date_limite": str(date_limite),
                        "hors_delai": len(anomalies) > 0,
                    },
                },
                self.name,
            ))

        return responses
