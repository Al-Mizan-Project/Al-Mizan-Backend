import logging
import math
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anomaly point weights (used for score_severite_global)
# ---------------------------------------------------------------------------
ANOMALY_POINTS: Dict[str, int] = {
    "MONTANT_FINANCIER_MANQUANT": 20,
    "MONTANT_INVALID": 20,
    "SOUMISSION_HORS_DELAI": 20,
    "ROTATION_SOUMISSIONNAIRES": 20,
    "MONTANT_TROP_ELEVE": 10,
    "PRIX_ANORMALEMENT_ELEVE": 10,
    "MONTANT_TROP_BAS": 10,
    "PRIX_ANORMALEMENT_BAS": 10,
    "DISPERSION_ANORMALE": 10,
}

# score_confiance: rule-based → 0.90–1.00
CONFIDENCE_SCORES: Dict[str, Decimal] = {
    "MONTANT_FINANCIER_MANQUANT": Decimal("1.00"),
    "MONTANT_INVALID": Decimal("1.00"),
    "SOUMISSION_HORS_DELAI": Decimal("1.00"),
    "MONTANT_TROP_ELEVE": Decimal("0.95"),
    "MONTANT_TROP_BAS": Decimal("0.95"),
    "PRIX_ANORMALEMENT_ELEVE": Decimal("0.92"),
    "PRIX_ANORMALEMENT_BAS": Decimal("0.90"),
    "DISPERSION_ANORMALE": Decimal("0.92"),
    "ROTATION_SOUMISSIONNAIRES": Decimal("0.90"),
}

# Severity classification: ERROR = blocking rule violation, WARNING = statistical
ANOMALY_SEVERITY: Dict[str, str] = {
    "MONTANT_FINANCIER_MANQUANT": "ERROR",
    "MONTANT_INVALID": "ERROR",
    "SOUMISSION_HORS_DELAI": "ERROR",
    "MONTANT_TROP_ELEVE": "WARNING",
    "MONTANT_TROP_BAS": "WARNING",
    "PRIX_ANORMALEMENT_ELEVE": "WARNING",
    "PRIX_ANORMALEMENT_BAS": "WARNING",
    "DISPERSION_ANORMALE": "WARNING",
    "ROTATION_SOUMISSIONNAIRES": "WARNING",
}

# Thresholds
RATIO_TROP_ELEVE = Decimal("3")          # montant > 3× montant_estime
RATIO_TROP_BAS = Decimal("0.70")         # montant < 70% of montant_estime
CV_DISPERSION_THRESHOLD = Decimal("0.02")  # std/mean < 2%
IQR_MULTIPLIER = Decimal("1.5")
MIN_SOUMISSIONS_FOR_STATS = 3


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _safe_decimal(value) -> Optional[Decimal]:
    """Safely convert a value to Decimal; returns None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_datetime(value) -> Optional[datetime]:
    """Parse ISO-format datetime string; returns None on failure."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def _std_dev(values: List[Decimal], mean: Decimal) -> Decimal:
    if len(values) < 2:
        return Decimal("0")
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return Decimal(str(math.sqrt(float(variance))))


def _iqr_bounds(values: List[Decimal]) -> Tuple[Decimal, Decimal]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    return q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr


def _make_anomaly(type_anomalie: str, id_soumission: int, details: str,
                  soumissions_impliquees: Optional[List[int]] = None) -> Dict:
    return {
        "id_soumission": id_soumission,
        "type_anomalie": type_anomalie,
        "niveau_severite": ANOMALY_SEVERITY[type_anomalie],
        "score_confiance": CONFIDENCE_SCORES[type_anomalie],
        "details": details,
        "soumissions_impliquees": soumissions_impliquees,
    }


# ---------------------------------------------------------------------------
# Individual detection algorithms
# ---------------------------------------------------------------------------
def _detect_montant_manquant(soumission: Dict, appel: Dict) -> Optional[Dict]:
    """
    MONTANT_FINANCIER_MANQUANT: montant_financier is NULL after the opening date.
    The opening date is considered to be date_limite_soumission (the bid deadline).
    """
    montant_raw = soumission.get("montant_financier")
    if montant_raw is not None:
        return None

    date_limite = _parse_datetime(appel.get("date_limite_soumission"))
    now = datetime.utcnow()
    if date_limite and now <= date_limite:
        # Opening not yet occurred — absence is expected
        return None

    return _make_anomaly(
        "MONTANT_FINANCIER_MANQUANT",
        int(soumission["id_soumission"]),
        (
            "Le champ montant_financier est NULL alors que la date d'ouverture des plis est dépassée. "
            "Aucun montant n'a été renseigné pour cette soumission, "
            "ce qui constitue une anomalie bloquante."
        ),
    )


def _detect_montant_invalid(soumission: Dict) -> Optional[Dict]:
    """MONTANT_INVALID: montant_financier is present but zero or negative."""
    montant = _safe_decimal(soumission.get("montant_financier"))
    if montant is None:
        return None  # handled by MONTANT_FINANCIER_MANQUANT
    if montant > 0:
        return None

    return _make_anomaly(
        "MONTANT_INVALID",
        int(soumission["id_soumission"]),
        (
            f"Le montant financier détecté ({montant:,.2f} DA) est invalide. "
            "La valeur doit être strictement supérieure à 0 conformément aux règles métier."
        ),
    )


def _detect_montant_trop_eleve(soumission: Dict, montant_estime: Optional[Decimal]) -> Optional[Dict]:
    """MONTANT_TROP_ELEVE: montant > 3× montant_estime."""
    if montant_estime is None or montant_estime <= 0:
        return None
    montant = _safe_decimal(soumission.get("montant_financier"))
    if montant is None or montant <= 0:
        return None

    ratio = montant / montant_estime
    if ratio <= RATIO_TROP_ELEVE:
        return None

    return _make_anomaly(
        "MONTANT_TROP_ELEVE",
        int(soumission["id_soumission"]),
        (
            f"Le montant financier ({montant:,.2f} DA) dépasse significativement "
            f"le montant estimé de l'appel d'offres ({montant_estime:,.2f} DA). "
            f"Ratio détecté : {ratio:.2f} (> 3). "
            "Cette situation peut indiquer une offre anormalement élevée."
        ),
    )


def _detect_montant_trop_bas(soumission: Dict, montant_estime: Optional[Decimal]) -> Optional[Dict]:
    """MONTANT_TROP_BAS: montant < 70% of montant_estime."""
    if montant_estime is None or montant_estime <= 0:
        return None
    montant = _safe_decimal(soumission.get("montant_financier"))
    if montant is None or montant <= 0:
        return None

    ratio = montant / montant_estime
    if ratio >= RATIO_TROP_BAS:
        return None

    return _make_anomaly(
        "MONTANT_TROP_BAS",
        int(soumission["id_soumission"]),
        (
            f"Le montant financier ({montant:,.2f} DA) est inférieur à 70% "
            f"du montant estimé ({montant_estime:,.2f} DA). "
            f"Ratio détecté : {ratio:.2f}. "
            "Risque de sous-évaluation ou d'offre techniquement irréaliste."
        ),
    )


def _detect_hors_delai(soumission: Dict, appel: Dict) -> Optional[Dict]:
    """SOUMISSION_HORS_DELAI: date_soumission > date_limite_soumission."""
    date_soumission = _parse_datetime(soumission.get("date_soumission"))
    date_limite = _parse_datetime(appel.get("date_limite_soumission"))

    if date_soumission is None or date_limite is None:
        return None
    if date_soumission <= date_limite:
        return None

    return _make_anomaly(
        "SOUMISSION_HORS_DELAI",
        int(soumission["id_soumission"]),
        (
            f"La soumission a été déposée le ({date_soumission.strftime('%Y-%m-%d %H:%M')}) "
            f"après la date limite fixée ({date_limite.strftime('%Y-%m-%d %H:%M')}). "
            "La soumission est considérée hors délai et potentiellement irrecevable."
        ),
    )


# ---------------------------------------------------------------------------
# Multi-soumission detectors
# ---------------------------------------------------------------------------
def _detect_prix_anormaux(soumissions: List[Dict], valid_montants: List[Decimal]) -> List[Dict]:
    """
    PRIX_ANORMALEMENT_ELEVE / PRIX_ANORMALEMENT_BAS:
    IQR-based outlier detection. Requires ≥ 3 soumissions with valid amounts.
    """
    anomalies = []
    if len(valid_montants) < MIN_SOUMISSIONS_FOR_STATS:
        return anomalies

    lower_bound, upper_bound = _iqr_bounds(valid_montants)
    mean = sum(valid_montants) / len(valid_montants)

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is None or montant <= 0:
            continue
        sid = int(soumission["id_soumission"])

        if montant > upper_bound:
            anomalies.append(_make_anomaly(
                "PRIX_ANORMALEMENT_ELEVE",
                sid,
                (
                    f"Le montant financier ({montant:,.2f} DA) est significativement supérieur "
                    f"aux autres offres soumises. Analyse statistique IQR révèle un écart important "
                    f"par rapport à la moyenne ({mean:,.2f} DA). "
                    "Cette situation peut correspondre à une offre de couverture ou à une surévaluation non justifiée."
                ),
            ))
        elif montant < lower_bound:
            anomalies.append(_make_anomaly(
                "PRIX_ANORMALEMENT_BAS",
                sid,
                (
                    f"Le montant financier ({montant:,.2f} DA) est significativement inférieur "
                    f"aux autres offres soumises. Analyse statistique IQR indique un écart anormal "
                    f"par rapport à la moyenne ({mean:,.2f} DA). "
                    "Cette situation peut indiquer une sous-évaluation, un risque de dumping "
                    "ou une offre techniquement irréaliste."
                ),
            ))

    return anomalies


def _detect_dispersion_anormale(soumissions: List[Dict], valid_montants: List[Decimal]) -> List[Dict]:
    """
    DISPERSION_ANORMALE: std/mean < 2% AND number of soumissions ≥ 3.
    Flags ALL soumissions with valid amounts.
    """
    anomalies = []
    if len(valid_montants) < MIN_SOUMISSIONS_FOR_STATS:
        return anomalies

    mean = sum(valid_montants) / len(valid_montants)
    if mean == 0:
        return anomalies

    std = _std_dev(valid_montants, mean)
    cv = std / mean

    if cv >= CV_DISPERSION_THRESHOLD:
        return anomalies

    cv_pct = float(cv * 100)
    all_ids = [
        int(s["id_soumission"])
        for s in soumissions
        if _safe_decimal(s.get("montant_financier")) is not None
    ]

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is None:
            continue
        anomalies.append(_make_anomaly(
            "DISPERSION_ANORMALE",
            int(soumission["id_soumission"]),
            (
                f"Les montants des soumissions présentent une faible dispersion. "
                f"Le coefficient de variation détecté ({cv_pct:.1f}%) est inférieur "
                f"au seuil défini ({float(CV_DISPERSION_THRESHOLD * 100):.0f}%). "
                "Cette homogénéité inhabituelle peut indiquer une coordination entre soumissionnaires."
            ),
            soumissions_impliquees=all_ids,
        ))

    return anomalies


def _detect_rotation_soumissionnaires(soumissions: List[Dict],
                                      historical_wins: List[Dict]) -> List[Dict]:
    """
    ROTATION_SOUMISSIONNAIRES: Requires ≥ 3 appels d'offres in history.
    Flags when wins are distributed quasi-uniformly among the same operators.

    historical_wins format:
        [{"id_appel_offre": int, "id_soumissionnaire": int, "id_soumission": int}, ...]
    """
    anomalies = []
    if not historical_wins or len(historical_wins) < 3:
        return anomalies

    # Deduplicate appels to count distinct contests
    distinct_appels = {w.get("id_appel_offre") for w in historical_wins if w.get("id_appel_offre")}
    if len(distinct_appels) < 3:
        return anomalies

    win_counts: Counter = Counter()
    for win in historical_wins:
        op_id = win.get("id_soumissionnaire")
        if op_id is not None:
            win_counts[op_id] += 1

    if len(win_counts) < 2:
        return anomalies

    counts = list(win_counts.values())
    avg_wins = sum(counts) / len(counts)
    max_deviation = max(abs(c - avg_wins) for c in counts)

    # Pattern: wins distributed quasi-uniformly (max deviation < 30% of avg)
    if avg_wins <= 0 or max_deviation / avg_wins >= Decimal("0.30"):
        return anomalies

    rotating_operators = set(win_counts.keys())
    distribution_str = ", ".join(f"Op{op}: {cnt}" for op, cnt in win_counts.items())

    for soumission in soumissions:
        op_id = soumission.get("id_soumissionnaire")
        if op_id not in rotating_operators:
            continue
        anomalies.append(_make_anomaly(
            "ROTATION_SOUMISSIONNAIRES",
            int(soumission["id_soumission"]),
            (
                f"Un schéma de rotation suspect a été détecté entre plusieurs opérateurs. "
                f"Les attributions de marchés sont réparties de manière quasi uniforme "
                f"entre les mêmes soumissionnaires ({{{distribution_str}}}). "
                "Ce comportement peut indiquer une entente."
            ),
            soumissions_impliquees=[
                int(s["id_soumission"])
                for s in soumissions
                if s.get("id_soumissionnaire") in rotating_operators
            ],
        ))

    return anomalies


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------
def _compute_score_severite(anomalies: List[Dict]) -> int:
    """score_severite_global = min(100, sum of anomaly points)."""
    total = sum(ANOMALY_POINTS.get(a["type_anomalie"], 0) for a in anomalies)
    return min(100, total)


def _score_to_niveau(score: int) -> str:
    if score >= 81:
        return "CRITIQUE"
    if score >= 51:
        return "ÉLEVÉ"
    if score >= 21:
        return "MOYEN"
    return "FAIBLE"


# ---------------------------------------------------------------------------
# Main orchestrator — single soumission
# ---------------------------------------------------------------------------
def detect_anomalies_soumission(
    soumission: Dict,
    appel: Dict,
    all_soumissions: List[Dict],
    historical_wins: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Run all anomaly detection rules for a single soumission.

    Parameters
    ----------
    soumission       : soumission dict (id_soumission, id_soumissionnaire,
                       id_appel_offre, montant_financier, date_soumission)
    appel            : appel dict (montant_estime, date_limite_soumission)
    all_soumissions  : ALL soumissions for the same appel (needed for multi rules)
    historical_wins  : list of past award dicts for rotation detection

    Returns
    -------
    dict with:
        anomalies            : list of anomaly dicts
        score_severite_global: int 0–100
        niveau_global        : str
        nb_errors            : int
        nb_warnings          : int
    """
    anomalies: List[Dict] = []
    montant_estime = _safe_decimal(appel.get("montant_estime"))

    # ── Single-soumission rules ──────────────────────────────────────────
    r = _detect_montant_manquant(soumission, appel)
    if r:
        anomalies.append(r)

    r = _detect_montant_invalid(soumission)
    if r:
        anomalies.append(r)

    # Only run ratio rules if amount is valid
    montant = _safe_decimal(soumission.get("montant_financier"))
    if montant is not None and montant > 0:
        r = _detect_montant_trop_eleve(soumission, montant_estime)
        if r:
            anomalies.append(r)

        r = _detect_montant_trop_bas(soumission, montant_estime)
        if r:
            anomalies.append(r)

    r = _detect_hors_delai(soumission, appel)
    if r:
        anomalies.append(r)

    # ── Multi-soumission rules (filter results to this soumission only) ──
    valid_montants = [
        m for s in all_soumissions
        if (m := _safe_decimal(s.get("montant_financier"))) is not None and m > 0
    ]

    sid = int(soumission["id_soumission"])

    # IQR outliers
    multi_prix = _detect_prix_anormaux(all_soumissions, valid_montants)
    anomalies.extend(a for a in multi_prix if a["id_soumission"] == sid)

    # Dispersion
    multi_disp = _detect_dispersion_anormale(all_soumissions, valid_montants)
    anomalies.extend(a for a in multi_disp if a["id_soumission"] == sid)

    # Rotation
    if historical_wins:
        multi_rot = _detect_rotation_soumissionnaires(all_soumissions, historical_wins)
        anomalies.extend(a for a in multi_rot if a["id_soumission"] == sid)

    score = _compute_score_severite(anomalies)
    nb_errors = sum(1 for a in anomalies if a["niveau_severite"] == "ERROR")
    nb_warnings = sum(1 for a in anomalies if a["niveau_severite"] == "WARNING")

    return {
        "anomalies": anomalies,
        "score_severite_global": score,
        "niveau_global": _score_to_niveau(score),
        "nb_errors": nb_errors,
        "nb_warnings": nb_warnings,
    }


# ---------------------------------------------------------------------------
# Main orchestrator — all soumissions for an appel d'offre
# ---------------------------------------------------------------------------
def detect_anomalies_appel(
    soumissions: List[Dict],
    appel: Dict,
    historical_wins: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Run anomaly detection over all soumissions for a given appel d'offre.

    Returns a flat list of all anomalies (one record per anomaly per soumission)
    plus a global resume.
    """
    if not soumissions:
        return {
            "anomalies": [],
            "total_soumissions_analysees": 0,
            "resume_global": {
                "total_anomalies": 0,
                "score_severite_global": 0,
                "niveau_global": "FAIBLE",
            },
        }

    montant_estime = _safe_decimal(appel.get("montant_estime"))

    # ── Compute multi-soumission results once ────────────────────────────
    valid_montants = [
        m for s in soumissions
        if (m := _safe_decimal(s.get("montant_financier"))) is not None and m > 0
    ]
    multi_prix_all = _detect_prix_anormaux(soumissions, valid_montants)
    multi_disp_all = _detect_dispersion_anormale(soumissions, valid_montants)
    multi_rot_all = (
        _detect_rotation_soumissionnaires(soumissions, historical_wins)
        if historical_wins else []
    )

    # Index multi-soumission results by soumission id
    def _index(lst: List[Dict]) -> Dict[int, List[Dict]]:
        idx: Dict[int, List[Dict]] = {}
        for a in lst:
            idx.setdefault(a["id_soumission"], []).append(a)
        return idx

    prix_idx = _index(multi_prix_all)
    disp_idx = _index(multi_disp_all)
    rot_idx = _index(multi_rot_all)

    all_anomalies: List[Dict] = []

    for soumission in soumissions:
        sid = int(soumission["id_soumission"])
        per_soum: List[Dict] = []

        # Single-soumission rules
        r = _detect_montant_manquant(soumission, appel)
        if r:
            per_soum.append(r)

        r = _detect_montant_invalid(soumission)
        if r:
            per_soum.append(r)

        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is not None and montant > 0:
            r = _detect_montant_trop_eleve(soumission, montant_estime)
            if r:
                per_soum.append(r)
            r = _detect_montant_trop_bas(soumission, montant_estime)
            if r:
                per_soum.append(r)

        r = _detect_hors_delai(soumission, appel)
        if r:
            per_soum.append(r)

        # Multi-soumission (pre-computed, filtered to this soumission)
        per_soum.extend(prix_idx.get(sid, []))
        per_soum.extend(disp_idx.get(sid, []))
        per_soum.extend(rot_idx.get(sid, []))

        all_anomalies.extend(per_soum)

    total = len(all_anomalies)
    total_pts = sum(ANOMALY_POINTS.get(a["type_anomalie"], 0) for a in all_anomalies)
    score_global = min(100, total_pts)

    return {
        "anomalies": all_anomalies,
        "total_soumissions_analysees": len(soumissions),
        "resume_global": {
            "total_anomalies": total,
            "score_severite_global": score_global,
            "niveau_global": _score_to_niveau(score_global),
        },
    }


# ---------------------------------------------------------------------------
# Legacy entry-point (kept for compatibility with existing callers)
# Wraps detect_anomalies_appel with a minimal appel dict.
# ---------------------------------------------------------------------------
def detect_price_and_similarity_anomalies(
    soumissions: List[Dict],
    montant_estime=None,
    historical_wins: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Legacy wrapper. Returns a flat list of anomaly dicts.
    Use detect_anomalies_appel() for new code.
    """
    appel: Dict = {}
    if montant_estime is not None:
        appel["montant_estime"] = montant_estime
    result = detect_anomalies_appel(soumissions, appel, historical_wins=historical_wins)
    return result["anomalies"]


# ---------------------------------------------------------------------------
# Summary report generator
# ---------------------------------------------------------------------------
def generate_anomaly_summary(anomalies: List[Dict], soumissions_count: int) -> Dict[str, Any]:
    """
    Build a summary dict from a list of anomaly dicts (as returned by
    detect_anomalies_appel or stored DetectionAnomalieIA records).
    """
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    nb_errors = 0
    nb_warnings = 0

    for a in anomalies:
        t = a.get("type_anomalie", "UNKNOWN")
        sev = a.get("niveau_severite", "WARNING")
        by_type[t] = by_type.get(t, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1
        if sev == "ERROR":
            nb_errors += 1
        else:
            nb_warnings += 1

    total_pts = sum(ANOMALY_POINTS.get(a.get("type_anomalie", ""), 0) for a in anomalies)
    score = min(100, total_pts)
    niveau = _score_to_niveau(score)

    return {
        "total_anomalies": len(anomalies),
        "nb_errors": nb_errors,
        "nb_warnings": nb_warnings,
        "score_severite_global": score,
        "niveau_global": niveau,
        "repartition_par_type": by_type,
        "repartition_par_severite": by_severity,
        "recommandation": _get_recommendation(niveau),
    }


def _get_recommendation(niveau: str) -> str:
    recommendations = {
        "CRITIQUE": (
            "ALERTE CRITIQUE : Fortes suspicions de fraude détectées. "
            "Il est recommandé de saisir la Commission des Marchés Publics "
            "et d'envisager l'annulation de la procédure."
        ),
        "ÉLEVÉ": (
            "ALERTE ÉLEVÉE : Anomalies significatives détectées. "
            "Un examen approfondi par la Commission d'Évaluation est nécessaire "
            "avant toute attribution."
        ),
        "MOYEN": (
            "ALERTE MODÉRÉE : Quelques indicateurs suspects relevés. "
            "La Commission d'Évaluation devrait examiner les offres concernées "
            "avec une attention particulière."
        ),
        "FAIBLE": (
            "Aucune anomalie critique détectée. Les offres semblent refléter "
            "une concurrence saine. Procéder à l'évaluation normale."
        ),
    }
    return recommendations.get(niveau, recommendations["FAIBLE"])