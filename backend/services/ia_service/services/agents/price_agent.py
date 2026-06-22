from decimal import Decimal
from typing import List, Optional

from ..anomalies import (
    _detect_montant_manquant,
    _detect_montant_invalid,
    _detect_montant_trop_eleve,
    _detect_montant_trop_bas,
    _detect_prix_anormaux,
    _safe_decimal,
)
from .base_agent import BaseAgent
from .message_bus import Message, MessageType


class PriceAgent(BaseAgent):
    """
    Agent spécialisé dans l'analyse des prix des soumissions.
    Détecte :
    - Montant manquant
    - Montant invalide (zéro ou négatif)
    - Montant trop élevé (> 3x estimation)
    - Montant trop bas (< 70% estimation)
    - Prix anormalement élevé/bas (IQR - outlier statistique)
    """

    def __init__(self):
        super().__init__(
            name="AgentPrix",
            role="Analyse des montants financiers et détection d'anomalies de prix",
        )

    def handle_message(self, message: Message) -> List[Message]:
        responses = []

        if message.type == MessageType.ANALYSE_PRIX:
            payload = message.payload
            soumission = payload.get("soumission", {})
            appel = payload.get("appel", {})
            all_soumissions = payload.get("all_soumissions", [])
            montant_estime = _safe_decimal(appel.get("montant_estime"))

            anomalies = []
            rules_applied = []

            r = _detect_montant_manquant(soumission, appel)
            if r:
                anomalies.append(r)
                rules_applied.append("montant_manquant")

            r = _detect_montant_invalid(soumission)
            if r:
                anomalies.append(r)
                rules_applied.append("montant_invalid")

            montant = _safe_decimal(soumission.get("montant_financier"))
            if montant is not None and montant > 0:
                r = _detect_montant_trop_eleve(soumission, montant_estime)
                if r:
                    anomalies.append(r)
                    rules_applied.append("montant_trop_eleve")

                r = _detect_montant_trop_bas(soumission, montant_estime)
                if r:
                    anomalies.append(r)
                    rules_applied.append("montant_trop_bas")

            # Analyse multi-soumission (IQR)
            valid_montants = [
                m for s in all_soumissions
                if (m := _safe_decimal(s.get("montant_financier"))) is not None and m > 0
            ]
            sid = int(soumission["id_soumission"])
            multi_prix = _detect_prix_anormaux(all_soumissions, valid_montants)
            for a in multi_prix:
                if a["id_soumission"] == sid:
                    anomalies.append(a)
                    rules_applied.append("prix_anormal")

            responses.append(message.reply(
                MessageType.RESULTAT_ANOMALIE,
                {
                    "agent": self.name,
                    "anomalies": anomalies,
                    "rules_applied": rules_applied,
                    "nb_anomalies": len(anomalies),
                    "analyse_detail": {
                        "montant_financier": float(montant) if montant else None,
                        "montant_estime": float(montant_estime) if montant_estime else None,
                        "nb_soumissions_analysees": len(all_soumissions),
                    },
                },
                self.name,
            ))

        return responses
