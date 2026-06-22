"""
Démo autonome du système multi-agent pour la détection d'anomalies.
Peut être exécutée en standalone pour la présentation :
    python demo_runner.py

Simule des données de soumission et exécute le pipeline complet
avec affichage de la trace de collaboration entre agents.

Fonctionne sans Django - utilise uniquement les modules agents et anomalies.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from services.ia_service.services.agents.orchestrator_agent import run_agent_pipeline

TS_FMT = "%Y-%m-%dT%H:%M:%S"
NOW = datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.strftime(TS_FMT)


def _make_soumission(id_soumission, montant_financier, id_soumissionnaire=1, **kwargs):
    return {
        "id_soumission": id_soumission,
        "id_soumissionnaire": id_soumissionnaire,
        "montant_financier": str(montant_financier) if montant_financier is not None else None,
        "date_soumission": kwargs.get("date_soumission", _ts(NOW)),
        **kwargs,
    }


def _make_appel(id_appel=1, montant_estime=50000000, **kwargs):
    return {
        "id_appel_offre": id_appel,
        "montant_estime": str(montant_estime),
        "date_limite_soumission": kwargs.get(
            "date_limite", _ts(NOW + timedelta(days=7))
        ),
        **kwargs,
    }


def scenario_1_soumission_normale():
    """Aucune anomalie - tout est conforme."""
    print("=" * 80)
    print("SCÉNARIO 1 : Soumission normale (aucune anomalie attendue)")
    print("=" * 80)

    soumission = _make_soumission(101, 45000000,
                                   date_soumission=_ts(NOW - timedelta(days=2)))
    appel = _make_appel(1, 50000000,
                        date_limite=_ts(NOW + timedelta(days=5)))
    all_soumissions = [
        _make_soumission(101, 45000000, date_soumission=_ts(NOW - timedelta(days=2))),
        _make_soumission(102, 48000000, date_soumission=_ts(NOW - timedelta(days=1))),
        _make_soumission(103, 52000000, date_soumission=_ts(NOW - timedelta(days=3))),
    ]

    rapport = run_agent_pipeline(soumission, appel, all_soumissions, trace=True)
    _afficher_rapport(rapport)
    return rapport


def scenario_2_prix_anormalement_bas():
    """Prix anormalement bas (< 70% de l'estimation)."""
    print("=" * 80)
    print("SCÉNARIO 2 : Prix anormalement bas (< 70% de l'estimation)")
    print("=" * 80)

    soumission = _make_soumission(201, 25000000,
                                   date_soumission=_ts(NOW - timedelta(days=2)))
    appel = _make_appel(2, 50000000,
                        date_limite=_ts(NOW + timedelta(days=5)))
    all_soumissions = [
        _make_soumission(201, 25000000, date_soumission=_ts(NOW - timedelta(days=2))),
        _make_soumission(202, 49000000, date_soumission=_ts(NOW - timedelta(days=1))),
        _make_soumission(203, 51000000, date_soumission=_ts(NOW - timedelta(days=3))),
        _make_soumission(204, 47500000, date_soumission=_ts(NOW - timedelta(days=4))),
    ]

    rapport = run_agent_pipeline(soumission, appel, all_soumissions, trace=True)
    _afficher_rapport(rapport)
    return rapport


def scenario_3_hors_delai():
    """Soumission déposée après la date limite."""
    print("=" * 80)
    print("SCÉNARIO 3 : Soumission hors délai")
    print("=" * 80)

    date_limite = _ts(NOW - timedelta(days=10))
    date_soumission = _ts(NOW - timedelta(days=5))

    soumission = _make_soumission(301, 45000000,
                                   date_soumission=date_soumission)
    appel = _make_appel(3, 50000000, date_limite=date_limite)
    all_soumissions = [
        _make_soumission(301, 45000000, date_soumission=date_soumission),
        _make_soumission(302, 48000000,
                         date_soumission=_ts(NOW - timedelta(days=12))),
    ]

    rapport = run_agent_pipeline(soumission, appel, all_soumissions, trace=True)
    _afficher_rapport(rapport)
    return rapport


def scenario_4_dispersion_anormale():
    """Dispersion anormale (CV < 2% - possible collusion)."""
    print("=" * 80)
    print("SCÉNARIO 4 : Dispersion anormale (CV < 2% - possible collusion)")
    print("=" * 80)

    soumission = _make_soumission(401, 49000000,
                                   date_soumission=_ts(NOW - timedelta(days=2)))
    appel = _make_appel(4, 50000000,
                        date_limite=_ts(NOW + timedelta(days=5)))
    all_soumissions = [
        _make_soumission(401, 49000000, date_soumission=_ts(NOW - timedelta(days=2))),
        _make_soumission(402, 49500000, date_soumission=_ts(NOW - timedelta(days=1))),
        _make_soumission(403, 49800000, date_soumission=_ts(NOW - timedelta(days=3))),
    ]

    rapport = run_agent_pipeline(soumission, appel, all_soumissions, trace=True)
    _afficher_rapport(rapport)
    return rapport


def scenario_5_rotation_soumissionnaires():
    """Rotation suspecte avec historique."""
    print("=" * 80)
    print("SCÉNARIO 5 : Rotation suspecte des soumissionnaires")
    print("=" * 80)

    soumission = _make_soumission(501, 47000000, id_soumissionnaire=10,
                                   date_soumission=_ts(NOW - timedelta(days=2)))
    appel = _make_appel(5, 50000000,
                        date_limite=_ts(NOW + timedelta(days=5)))
    all_soumissions = [
        _make_soumission(501, 47000000, id_soumissionnaire=10,
                         date_soumission=_ts(NOW - timedelta(days=2))),
        _make_soumission(502, 49000000, id_soumissionnaire=20,
                         date_soumission=_ts(NOW - timedelta(days=1))),
        _make_soumission(503, 51000000, id_soumissionnaire=30,
                         date_soumission=_ts(NOW - timedelta(days=3))),
    ]
    historical_wins = [
        {"id_appel_offre": 1, "id_soumissionnaire": 10, "id_soumission": 1},
        {"id_appel_offre": 2, "id_soumissionnaire": 20, "id_soumission": 2},
        {"id_appel_offre": 3, "id_soumissionnaire": 30, "id_soumission": 3},
        {"id_appel_offre": 4, "id_soumissionnaire": 10, "id_soumission": 4},
        {"id_appel_offre": 5, "id_soumissionnaire": 20, "id_soumission": 5},
    ]

    rapport = run_agent_pipeline(
        soumission, appel, all_soumissions,
        historical_wins=historical_wins, trace=True,
    )
    _afficher_rapport(rapport)
    return rapport


def _afficher_rapport(rapport: dict) -> None:
    resume = rapport.get("resume", {})
    anomalies = rapport.get("anomalies", [])
    collaboration = rapport.get("collaboration", {})
    trace = rapport.get("trace_collaboration", {})

    print()
    print("  RÉSULTATS")
    print(f"  Score de sévérité : {resume.get('score_severite_global', 0)}/100 "
          f"({resume.get('niveau_global', 'N/A')})")
    print(f"  Anomalies : {resume.get('total_anomalies', 0)} "
          f"(Erreurs: {resume.get('nb_errors', 0)}, "
          f"Avertissements: {resume.get('nb_warnings', 0)})")

    if anomalies:
        print()
        print("  ANOMALIES DÉTECTÉES :")
        for a in anomalies:
            sev = "🔴" if a.get("niveau_severite") == "ERROR" else "🟡"
            print(f"    {sev} {a.get('type_anomalie', '?')} "
                  f"(confiance: {float(a.get('score_confiance', 0)):.0%})")
            details = a.get('details', '')
            print(f"       {details[:120]}..." if len(details) > 120 else f"       {details}")

    print()
    print("  COLLABORATION MULTI-AGENTS :")
    print(f"  {collaboration.get('description', '')}")
    distribution = collaboration.get("distribution_travail", {})
    for agent_name, details in distribution.items():
        anomalies_count = details.get("anomalies_trouvees", 0)
        regles = details.get("regles_appliquees", [])
        icon = "✅" if anomalies_count > 0 else "ℹ️"
        print(f"    {icon} {agent_name}: {anomalies_count} anomalie(s), "
              f"règles: {', '.join(regles) if regles else 'aucune'}")

    if trace:
        print()
        print("  TRACE DE COMMUNICATION :")
        print(f"  Messages échangés: {trace.get('stats', {}).get('total_messages', 0)}")
        exchanges = trace.get('stats', {}).get('exchanges', {})
        for exchange, count in exchanges.items():
            print(f"    {exchange}: {count} message(s)")

    print()
    print("  TRACE DÉTAILLÉE :")
    print(trace.get('visualisation', '(non disponible)'))
    print()


def run_all_scenarios():
    """Exécute tous les scénarios de démonstration."""
    scenarios = [
        ("Scénario 1 : Soumission normale", scenario_1_soumission_normale),
        ("Scénario 2 : Prix anormalement bas", scenario_2_prix_anormalement_bas),
        ("Scénario 3 : Hors délai", scenario_3_hors_delai),
        ("Scénario 4 : Dispersion anormale", scenario_4_dispersion_anormale),
        ("Scénario 5 : Rotation suspecte", scenario_5_rotation_soumissionnaires),
    ]

    for title, scenario_fn in scenarios:
        print()
        print(f"{'#' * 80}")
        print(f"# {title}")
        print(f"{'#' * 80}")
        try:
            scenario_fn()
        except Exception as e:
            print(f"  ❌ Erreur dans '{title}': {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 80)
    print("DÉMONSTRATION DU SYSTÈME MULTI-AGENT TERMINÉE")
    print("=" * 80)
    print()
    print("Rappel de l'architecture :")
    print("  Orchestrateur → distribue les sous-tâches → agents spécialisés")
    print("  AgentPrix      → analyse des montants financiers")
    print("  AgentDelai     → vérification des délais de soumission")
    print("  AgentDispersion → détection de dispersion anormale (collusion)")
    print("  AgentRotation  → détection de rotation des soumissionnaires")
    print()
    print("Chaque agent est indépendant et utilise ses propres règles métier.")
    print("L'Orchestrateur agrège les résultats et calcule le score global.")


if __name__ == "__main__":
    run_all_scenarios()
