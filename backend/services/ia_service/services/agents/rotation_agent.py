from typing import List, Optional

from ..anomalies import _detect_rotation_soumissionnaires
from .base_agent import BaseAgent
from .message_bus import Message, MessageType


class RotationAgent(BaseAgent):
    """
    Agent spécialisé dans la détection de rotation suspecte des soumissionnaires.
    Détecte :
    - Distribution quasi-uniforme des marchés entre les mêmes opérateurs
      (indice d'entente ou de répartition de marchés)
    - Nécessite ≥ 3 appels d'offres historiques
    """

    def __init__(self):
        super().__init__(
            name="AgentRotation",
            role="Détection de schémas de rotation entre soumissionnaires",
        )

    def handle_message(self, message: Message) -> List[Message]:
        responses = []

        if message.type == MessageType.ANALYSE_ROTATION:
            payload = message.payload
            soumission = payload.get("soumission", {})
            all_soumissions = payload.get("all_soumissions", [])
            historical_wins = payload.get("historical_wins")

            anomalies = []
            rules_applied = []
            stats = {}

            if historical_wins:
                multi_rot = _detect_rotation_soumissionnaires(all_soumissions, historical_wins)
                sid = int(soumission["id_soumission"])
                for a in multi_rot:
                    if a["id_soumission"] == sid:
                        anomalies.append(a)
                        rules_applied.append("rotation_soumissionnaires")

                wins_count = len(historical_wins)
                distinct_ops = len(set(
                    w.get("id_soumissionnaire") for w in historical_wins
                    if w.get("id_soumissionnaire")
                ))
                stats = {
                    "marches_historiques": wins_count,
                    "soumissionnaires_distincts": distinct_ops,
                    "rotation_detectee": len(anomalies) > 0,
                }

            responses.append(message.reply(
                MessageType.RESULTAT_ANOMALIE,
                {
                    "agent": self.name,
                    "anomalies": anomalies,
                    "rules_applied": rules_applied,
                    "nb_anomalies": len(anomalies),
                    "analyse_detail": stats,
                },
                self.name,
            ))

        return responses
