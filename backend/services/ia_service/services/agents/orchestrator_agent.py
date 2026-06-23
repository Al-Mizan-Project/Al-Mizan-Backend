from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..anomalies import (
    ANOMALY_POINTS,
    _compute_score_severite,
    _score_to_niveau,
    _safe_decimal,
    generate_anomaly_summary,
)
from .base_agent import BaseAgent
from .message_bus import Message, MessageBus, MessageType
from .trace_collector import TraceCollector
from .price_agent import PriceAgent
from .deadline_agent import DeadlineAgent
from .dispersion_agent import DispersionAgent
from .rotation_agent import RotationAgent


class OrchestratorAgent(BaseAgent):
    """
    Agent coordinateur principal du système multi-agent.
    Responsabilités :
    1. Recevoir les requêtes de détection
    2. Décomposer le travail en sous-tâches et les distribuer aux agents spécialisés
    3. Collecter et agréger les résultats
    4. Calculer le score de sévérité global
    5. Produire un rapport final structuré
    6. Optionnel : journaliser toute la trace de collaboration
    """

    def __init__(self, trace_collector: Optional[TraceCollector] = None):
        super().__init__(
            name="Orchestrateur",
            role="Agent coordinateur - décomposition, distribution et agrégation des analyses",
        )
        self.trace_collector = trace_collector

    def handle_message(self, message: Message) -> List[Message]:
        responses = []

        if message.type == MessageType.DETECTION_REQUEST:
            result = self._run_pipeline(message)
            responses.append(message.reply(
                MessageType.RAPPORT_FINAL,
                result,
                self.name,
            ))

        return responses

    def _run_pipeline(self, message: Message) -> Dict[str, Any]:
        payload = message.payload
        soumission = payload.get("soumission", {})
        appel = payload.get("appel", {})
        all_soumissions = payload.get("all_soumissions", [])
        historical_wins = payload.get("historical_wins")
        commission_type = payload.get("commission_type", "interne")

        if self.trace_collector:
            self.send_log("info", f"Début du pipeline de détection pour soumission #{soumission.get('id_soumission')}")

        # Étape 1 : Distribuer les analyses aux agents spécialisés en parallèle
        tasks = [
            (MessageType.ANALYSE_PRIX, {
                "soumission": soumission,
                "appel": appel,
                "all_soumissions": all_soumissions,
            }),
            (MessageType.ANALYSE_DELAI, {
                "soumission": soumission,
                "appel": appel,
            }),
            (MessageType.ANALYSE_DISPERSION, {
                "soumission": soumission,
                "all_soumissions": all_soumissions,
            }),
        ]

        if historical_wins:
            tasks.append((MessageType.ANALYSE_ROTATION, {
                "soumission": soumission,
                "all_soumissions": all_soumissions,
                "historical_wins": historical_wins,
            }))

        # Envoyer les tâches et collecter les résultats
        agent_results = []
        for msg_type, task_payload in tasks:
            task_msg = Message(
                type=msg_type,
                payload=task_payload,
                sender=self.name,
            )
            if self.trace_collector:
                self.trace_collector.record(task_msg)

            responses = self.bus.send(task_msg)

            if self.trace_collector:
                self.trace_collector.record_batch(responses, direction="receive")

            for resp in responses:
                if resp.type == MessageType.RESULTAT_ANOMALIE:
                    agent_results.append(resp.payload)

        if self.trace_collector:
            self.send_log("info", f"Résultats reçus de {len(agent_results)} agents spécialisés")

        # Étape 2 : Agréger les résultats
        all_anomalies = []
        agent_details = []

        for result in agent_results:
            all_anomalies.extend(result.get("anomalies", []))
            agent_details.append({
                "agent": result.get("agent"),
                "nb_anomalies": result.get("nb_anomalies", 0),
                "regles_appliquees": result.get("rules_applied", []),
                "analyse_detail": result.get("analyse_detail", {}),
            })

        # Étape 3 : Calculer le score global
        score = _compute_score_severite(all_anomalies)
        niveau = _score_to_niveau(score)

        nb_errors = sum(1 for a in all_anomalies if a.get("niveau_severite") == "ERROR")
        nb_warnings = sum(1 for a in all_anomalies if a.get("niveau_severite") == "WARNING")

        # Étape 4 : Générer le rapport
        rapport = self._build_rapport(
            soumission=soumission,
            appel=appel,
            anomalies=all_anomalies,
            score=score,
            niveau=niveau,
            nb_errors=nb_errors,
            nb_warnings=nb_warnings,
            agent_details=agent_details,
            commission_type=commission_type,
        )

        if self.trace_collector:
            self.send_log("info", f"Pipeline terminé - {len(all_anomalies)} anomalies trouvées, score: {score}")

        return rapport

    def _build_rapport(
        self,
        soumission: Dict,
        appel: Dict,
        anomalies: List[Dict],
        score: int,
        niveau: str,
        nb_errors: int,
        nb_warnings: int,
        agent_details: List[Dict],
        commission_type: str,
    ) -> Dict[str, Any]:
        return {
            "id_soumission": int(soumission.get("id_soumission", 0)),
            "id_appel_offre": int(appel.get("id_appel_offre", 0)),
            "commission_type": commission_type,
            "resume": {
                "total_anomalies": len(anomalies),
                "nb_errors": nb_errors,
                "nb_warnings": nb_warnings,
                "score_severite_global": score,
                "niveau_global": niveau,
            },
            "anomalies": anomalies,
            "analyse_multi_agents": {
                "nb_agents_sollicites": len(agent_details),
                "details_par_agent": agent_details,
            },
            "collaboration": self._build_collaboration_section(agent_details),
        }

    def _build_collaboration_section(self, agent_details: List[Dict]) -> Dict[str, Any]:
        total_anomalies = sum(a.get("nb_anomalies", 0) for a in agent_details)
        agents_ayant_trouve = [a for a in agent_details if a.get("nb_anomalies", 0) > 0]

        return {
            "description": (
                "L'Orchestrateur a décomposé la demande d'analyse en sous-tâches "
                "et distribué chaque sous-tâche à l'agent spécialisé correspondant. "
                "Chaque agent a exécuté ses règles métier de façon indépendante et "
                "retourné ses résultats à l'Orchestrateur qui les a agrégés."
            ),
            "distribution_travail": {
                agent["agent"]: {
                    "anomalies_trouvees": agent["nb_anomalies"],
                    "regles_appliquees": agent["regles_appliquees"],
                }
                for agent in agent_details
            },
            "total_anomalies_collectees": total_anomalies,
            "agents_contributeurs": [a["agent"] for a in agents_ayant_trouve],
        }


def run_agent_pipeline(
    soumission: Dict,
    appel: Dict,
    all_soumissions: List[Dict],
    historical_wins: Optional[List[Dict]] = None,
    commission_type: str = "interne",
    trace: bool = True,
) -> Dict[str, Any]:
    """
    Point d'entrée principal pour exécuter le pipeline multi-agent.
    Configure le bus, enregistre les agents, et lance la détection.

    Retourne le rapport final avec les anomalies et la trace de collaboration.
    """
    bus = MessageBus()
    trace_collector = TraceCollector() if trace else None

    orchestrator = OrchestratorAgent(trace_collector=trace_collector)
    price_agent = PriceAgent()
    deadline_agent = DeadlineAgent()
    dispersion_agent = DispersionAgent()
    rotation_agent = RotationAgent()

    for agent in [orchestrator, price_agent, deadline_agent, dispersion_agent, rotation_agent]:
        bus.register(agent)

    bus.subscribe("Orchestrateur", MessageType.DETECTION_REQUEST)
    bus.subscribe("AgentPrix", MessageType.ANALYSE_PRIX)
    bus.subscribe("AgentDelai", MessageType.ANALYSE_DELAI)
    bus.subscribe("AgentDispersion", MessageType.ANALYSE_DISPERSION)
    bus.subscribe("AgentRotation", MessageType.ANALYSE_ROTATION)

    request = Message(
        type=MessageType.DETECTION_REQUEST,
        payload={
            "soumission": soumission,
            "appel": appel,
            "all_soumissions": all_soumissions,
            "historical_wins": historical_wins,
            "commission_type": commission_type,
        },
        sender="system",
    )

    if trace:
        trace_collector.record(request)

    responses = bus.send(request)

    rapport = None
    for resp in responses:
        if resp.type == MessageType.RAPPORT_FINAL:
            rapport = resp.payload
            break

    if rapport is None:
        rapport = {
            "error": "Aucun rapport produit par l'Orchestrateur",
            "anomalies": [],
            "resume": {"total_anomalies": 0},
        }

    if trace:
        rapport["trace_collaboration"] = {
            "journal": trace_collector.get_trace(),
            "stats": trace_collector.summary(),
            "visualisation": trace_collector.get_formatted_trace(),
        }

    return rapport
