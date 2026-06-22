from decimal import Decimal
from typing import List

from ..anomalies import _detect_dispersion_anormale, _safe_decimal
from .base_agent import BaseAgent
from .message_bus import Message, MessageType


class DispersionAgent(BaseAgent):
    """
    Agent spécialisé dans la détection de dispersion anormale des prix.
    Détecte :
    - Coefficient de variation < 2% entre les soumissions (signe de coordination)
    - Nécessite ≥ 3 soumissions avec montants valides
    """

    def __init__(self):
        super().__init__(
            name="AgentDispersion",
            role="Détection de dispersion anormale des prix (collusion)",
        )

    def handle_message(self, message: Message) -> List[Message]:
        responses = []

        if message.type == MessageType.ANALYSE_DISPERSION:
            payload = message.payload
            soumission = payload.get("soumission", {})
            all_soumissions = payload.get("all_soumissions", [])

            valid_montants = [
                m for s in all_soumissions
                if (m := _safe_decimal(s.get("montant_financier"))) is not None and m > 0
            ]

            anomalies = []
            rules_applied = []
            stats = {}

            if len(valid_montants) >= 3:
                multi_disp = _detect_dispersion_anormale(all_soumissions, valid_montants)
                sid = int(soumission["id_soumission"])
                for a in multi_disp:
                    if a["id_soumission"] == sid:
                        anomalies.append(a)
                        rules_applied.append("dispersion_anormale")

                # Calculer les stats pour le rapport
                mean = sum(valid_montants) / len(valid_montants)
                std = self._std_dev(valid_montants, mean)
                cv = float(std / mean * 100) if mean > 0 else 0
                stats = {
                    "moyenne": float(mean),
                    "ecart_type": float(std),
                    "coefficient_variation_pct": round(cv, 2),
                    "seuil_cv": 2.0,
                    "dispersion_anormale": cv < 2.0,
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

    def _std_dev(self, values: List[Decimal], mean: Decimal) -> Decimal:
        import math
        if len(values) < 2:
            return Decimal("0")
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return Decimal(str(math.sqrt(float(variance))))
