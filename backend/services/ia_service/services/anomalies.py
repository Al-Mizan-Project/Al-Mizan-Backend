"""
Anomaly Detection Engine for Al-Mizan Public Procurement Platform.

Implements predictive algorithms to detect:
- Collusion suspicions (similar offers, price-fixing agreements)
- Price clustering (offers suspiciously close to each other)
- Bid rotation patterns (same operators winning in turns)
- Document similarity (identical technical proposals)
- Statistical outliers (abnormal pricing patterns)

Algorithms used:
- Z-Score analysis for statistical deviation
- IQR (Interquartile Range) for robust outlier detection
- Pairwise similarity for collusion clustering
- Coefficient of variation for price dispersion analysis
"""
import logging
import math
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration thresholds
# ---------------------------------------------------------------------------
# Price similarity: if two offers are within this % of each other
PRICE_SIMILARITY_THRESHOLD = Decimal("0.005")  # 0.5%

# Price clustering: if the Coefficient of Variation of ALL offers is below this
CV_COLLUSION_THRESHOLD = Decimal("0.02")  # 2% — very suspicious for public tenders

# Z-Score threshold: flag offers beyond this many standard deviations
ZSCORE_THRESHOLD = Decimal("2.5")

# IQR multiplier for outlier detection
IQR_MULTIPLIER = Decimal("1.5")

# Pairwise price proximity threshold
PAIRWISE_PROXIMITY_THRESHOLD = Decimal("0.01")  # 1%

# Round-number bias threshold (offers ending in 000s)
ROUND_NUMBER_MODULO = 1000

# Minimum number of soumissions needed for statistical analysis
MIN_SOUMISSIONS_FOR_STATS = 3

# Score weights for confidence calculation
CONFIDENCE_WEIGHTS = {
    "SIMILARITE_PRIX": Decimal("0.85"),
    "SIMILARITE_DOCUMENTAIRE": Decimal("0.78"),
    "COLLUSION_CLUSTER_PRIX": Decimal("0.92"),
    "ROTATION_SOUMISSIONNAIRES": Decimal("0.75"),
    "PRIX_ANORMALEMENT_BAS": Decimal("0.80"),
    "PRIX_ANORMALEMENT_ELEVE": Decimal("0.70"),
    "BIAIS_NOMBRES_RONDS": Decimal("0.60"),
    "OFFRES_COMPLEMENTAIRES": Decimal("0.88"),
    "DISPERSION_ANORMALE": Decimal("0.82"),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _safe_decimal(value) -> Optional[Decimal]:
    """Safely convert a value to Decimal."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _median(values: List[Decimal]) -> Decimal:
    """Calculate the median of a list of Decimal values."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0:
        return Decimal("0")
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]


def _std_dev(values: List[Decimal], mean: Decimal) -> Decimal:
    """Calculate standard deviation of Decimal values."""
    if len(values) < 2:
        return Decimal("0")
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    # Use float sqrt and convert back (Decimal doesn't have sqrt)
    return Decimal(str(math.sqrt(float(variance))))


def _iqr_bounds(values: List[Decimal]) -> Tuple[Decimal, Decimal]:
    """Calculate IQR-based lower and upper bounds for outlier detection."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1_idx = n // 4
    q3_idx = (3 * n) // 4
    q1 = sorted_vals[q1_idx]
    q3 = sorted_vals[q3_idx]
    iqr = q3 - q1
    lower_bound = q1 - IQR_MULTIPLIER * iqr
    upper_bound = q3 + IQR_MULTIPLIER * iqr
    return lower_bound, upper_bound


# ---------------------------------------------------------------------------
# Individual detection algorithms
# ---------------------------------------------------------------------------
def _detect_document_similarity(soumissions: List[Dict]) -> List[Dict]:
    """
    Detect soumissions with identical document signatures.
    This suggests operators may have shared or copied proposals,
    a strong indicator of collusion.
    """
    anomalies = []
    by_hash: Dict[str, List[Dict]] = {}

    for soumission in soumissions:
        signature = str(soumission.get("signature_document", "")).strip()
        if signature:
            by_hash.setdefault(signature, []).append(soumission)

    for signature, items in by_hash.items():
        if len(items) < 2:
            continue
        colluding_ids = [int(s["id_soumission"]) for s in items]
        for soumission in items:
            anomalies.append({
                "id_soumission": int(soumission["id_soumission"]),
                "type_anomalie": "SIMILARITE_DOCUMENTAIRE",
                "niveau_severite": "ELEVEE",
                "score_confiance": CONFIDENCE_WEIGHTS["SIMILARITE_DOCUMENTAIRE"],
                "details": (
                    f"Signature documentaire identique détectée ({signature[:16]}...). "
                    f"Soumissions concernées: {colluding_ids}. "
                    f"Cela pourrait indiquer un partage de documents entre soumissionnaires."
                ),
                "soumissions_impliquees": colluding_ids,
            })

    return anomalies


def _detect_price_similarity_to_mean(soumissions: List[Dict], montants: List[Decimal], moyenne: Decimal) -> List[Dict]:
    """
    Detect offers whose financial amount is suspiciously close to the 
    collective average — a sign of price-fixing (entente sur les prix).
    """
    anomalies = []
    if moyenne is None or moyenne == 0:
        return anomalies

    candidates = []

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is None:
            continue
        ecart_relatif = abs(montant - moyenne) / moyenne
        if ecart_relatif <= PRICE_SIMILARITY_THRESHOLD:
            candidates.append({
                "id_soumission": int(soumission["id_soumission"]),
                "type_anomalie": "SIMILARITE_PRIX",
                "niveau_severite": "ELEVEE",
                "score_confiance": CONFIDENCE_WEIGHTS["SIMILARITE_PRIX"],
                "details": (
                    f"Montant financier ({montant:,.2f} DA) très proche de la moyenne "
                    f"collective ({moyenne:,.2f} DA). Écart relatif: {ecart_relatif * 100:.3f}%. "
                    f"Seuil de détection: {PRICE_SIMILARITY_THRESHOLD * 100}%."
                ),
            })

    # A single offer close to the mean is normal; alert only if multiple offers cluster there.
    if len(candidates) >= 2:
        anomalies.extend(candidates)

    return anomalies


def _detect_pairwise_price_proximity(soumissions: List[Dict]) -> List[Dict]:
    """
    Detect pairs of offers that are suspiciously close in price.
    Unlike mean-based detection, this catches bilateral collusion even
    when the average is skewed by a cover bid.
    """
    anomalies = []
    entries = []

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is not None and montant > 0:
            entries.append((int(soumission["id_soumission"]), montant))

    for (id_a, montant_a), (id_b, montant_b) in combinations(entries, 2):
        reference = max(montant_a, montant_b)
        ecart = abs(montant_a - montant_b) / reference
        if ecart <= PAIRWISE_PROXIMITY_THRESHOLD:
            anomalies.append({
                "id_soumission": id_a,
                "type_anomalie": "COLLUSION_CLUSTER_PRIX",
                "niveau_severite": "ELEVEE",
                "score_confiance": CONFIDENCE_WEIGHTS["COLLUSION_CLUSTER_PRIX"],
                "details": (
                    f"Proximité de prix suspecte avec la soumission #{id_b}. "
                    f"Montant A: {montant_a:,.2f} DA, Montant B: {montant_b:,.2f} DA. "
                    f"Écart: {ecart * 100:.3f}% (seuil: {PAIRWISE_PROXIMITY_THRESHOLD * 100}%)."
                ),
                "soumissions_impliquees": [id_a, id_b],
            })
            anomalies.append({
                "id_soumission": id_b,
                "type_anomalie": "COLLUSION_CLUSTER_PRIX",
                "niveau_severite": "ELEVEE",
                "score_confiance": CONFIDENCE_WEIGHTS["COLLUSION_CLUSTER_PRIX"],
                "details": (
                    f"Proximité de prix suspecte avec la soumission #{id_a}. "
                    f"Montant A: {montant_a:,.2f} DA, Montant B: {montant_b:,.2f} DA. "
                    f"Écart: {ecart * 100:.3f}% (seuil: {PAIRWISE_PROXIMITY_THRESHOLD * 100}%)."
                ),
                "soumissions_impliquees": [id_a, id_b],
            })

    return anomalies


def _detect_low_dispersion(montants: List[Decimal], soumissions: List[Dict]) -> List[Dict]:
    """
    Detect abnormally low price dispersion across all offers.
    If the Coefficient of Variation is too low, it suggests
    coordinated pricing (entente on prices).
    """
    anomalies = []
    if len(montants) < MIN_SOUMISSIONS_FOR_STATS:
        return anomalies

    moyenne = sum(montants) / len(montants)
    if moyenne == 0:
        return anomalies

    std = _std_dev(montants, moyenne)
    cv = std / moyenne

    if cv < CV_COLLUSION_THRESHOLD:
        all_ids = [int(s["id_soumission"]) for s in soumissions if _safe_decimal(s.get("montant_financier")) is not None]
        for soumission in soumissions:
            montant = _safe_decimal(soumission.get("montant_financier"))
            if montant is None:
                continue
            anomalies.append({
                "id_soumission": int(soumission["id_soumission"]),
                "type_anomalie": "DISPERSION_ANORMALE",
                "niveau_severite": "ELEVEE",
                "score_confiance": CONFIDENCE_WEIGHTS["DISPERSION_ANORMALE"],
                "details": (
                    f"Coefficient de variation anormalement bas ({cv * 100:.2f}%) "
                    f"sur {len(montants)} offres. Seuil: {CV_COLLUSION_THRESHOLD * 100}%. "
                    f"Moyenne: {moyenne:,.2f} DA, Écart-type: {std:,.2f} DA. "
                    f"Cela suggère une entente sur les prix entre tous les soumissionnaires."
                ),
                "soumissions_impliquees": all_ids,
            })

    return anomalies


def _detect_statistical_outliers(soumissions: List[Dict], montants: List[Decimal], moyenne: Decimal) -> List[Dict]:
    """
    Detect statistically abnormal prices using Z-Score and IQR methods.
    Flags both abnormally low prices (possible predatory bidding) and
    abnormally high prices (cover bids in collusion schemes).
    """
    anomalies = []
    if len(montants) < MIN_SOUMISSIONS_FOR_STATS:
        return anomalies

    std = _std_dev(montants, moyenne)
    lower_bound, upper_bound = _iqr_bounds(montants)
    mediane = _median(montants)
    robust_low_ratio = Decimal("0.55")
    robust_high_ratio = Decimal("1.80")

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is None:
            continue

        z_score = (montant - moyenne) / std if std != 0 else Decimal("0")
        low_by_robust_ratio = mediane > 0 and montant <= (mediane * robust_low_ratio)
        high_by_robust_ratio = mediane > 0 and montant >= (mediane * robust_high_ratio)

        # Abnormally LOW price
        if z_score < -ZSCORE_THRESHOLD or montant < lower_bound or low_by_robust_ratio:
            anomalies.append({
                "id_soumission": int(soumission["id_soumission"]),
                "type_anomalie": "PRIX_ANORMALEMENT_BAS",
                "niveau_severite": "MOYEN",
                "score_confiance": CONFIDENCE_WEIGHTS["PRIX_ANORMALEMENT_BAS"],
                "details": (
                    f"Prix anormalement bas détecté. Montant: {montant:,.2f} DA, "
                    f"Moyenne: {moyenne:,.2f} DA, Z-Score: {z_score:.2f}. "
                    f"Borne inférieure IQR: {lower_bound:,.2f} DA. "
                    f"Risque de dumping ou offre techniquement irréaliste."
                ),
            })

        # Abnormally HIGH price (potential cover bid)
        elif z_score > ZSCORE_THRESHOLD or montant > upper_bound or high_by_robust_ratio:
            anomalies.append({
                "id_soumission": int(soumission["id_soumission"]),
                "type_anomalie": "PRIX_ANORMALEMENT_ELEVE",
                "niveau_severite": "MOYEN",
                "score_confiance": CONFIDENCE_WEIGHTS["PRIX_ANORMALEMENT_ELEVE"],
                "details": (
                    f"Prix anormalement élevé détecté. Montant: {montant:,.2f} DA, "
                    f"Moyenne: {moyenne:,.2f} DA, Z-Score: {z_score:.2f}. "
                    f"Borne supérieure IQR: {upper_bound:,.2f} DA. "
                    f"Possible offre de couverture dans un schéma de collusion."
                ),
            })

    return anomalies


def _detect_complementary_bids(soumissions: List[Dict], montant_estime: Optional[Decimal] = None) -> List[Dict]:
    """
    Detect complementary bidding patterns (offres de couverture).
    In this pattern, one bidder submits a realistic offer while 
    others submit intentionally high bids to make the target bid 
    appear competitive.
    
    Indicators:
    - One offer is significantly lower than all others
    - The other offers are clustered together at a higher range
    - The lowest offer is close to the estimated amount (if known)
    """
    anomalies = []
    entries = []

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is not None and montant > 0:
            entries.append((int(soumission["id_soumission"]), montant))

    if len(entries) < 3:
        return anomalies

    entries.sort(key=lambda x: x[1])
    lowest_id, lowest_montant = entries[0]
    rest_montants = [m for _, m in entries[1:]]
    rest_mean = sum(rest_montants) / len(rest_montants)

    if rest_mean == 0:
        return anomalies

    # Check if the gap between lowest and second lowest is disproportionate
    gap_ratio = (entries[1][1] - lowest_montant) / rest_mean

    # Check if the remaining offers are tightly clustered
    rest_std = _std_dev(rest_montants, rest_mean)
    rest_cv = rest_std / rest_mean if rest_mean > 0 else Decimal("1")

    # Pattern: large gap from lowest to rest + rest are tightly grouped
    if gap_ratio > Decimal("0.15") and rest_cv < Decimal("0.05"):
        # Flag the cover bidders
        cover_ids = [eid for eid, _ in entries[1:]]
        for eid, emontant in entries[1:]:
            anomalies.append({
                "id_soumission": eid,
                "type_anomalie": "OFFRES_COMPLEMENTAIRES",
                "niveau_severite": "ELEVEE",
                "score_confiance": CONFIDENCE_WEIGHTS["OFFRES_COMPLEMENTAIRES"],
                "details": (
                    f"Suspicion d'offre de couverture. Ce montant ({emontant:,.2f} DA) "
                    f"fait partie d'un cluster de {len(cover_ids)} offres élevées "
                    f"(CV: {rest_cv * 100:.2f}%) tandis qu'une offre significativement "
                    f"plus basse ({lowest_montant:,.2f} DA) existe. "
                    f"Écart: {gap_ratio * 100:.1f}%."
                ),
                "soumissions_impliquees": [lowest_id] + cover_ids,
            })

    return anomalies


def _detect_round_number_bias(soumissions: List[Dict]) -> List[Dict]:
    """
    Detect if offers are suspiciously rounded, suggesting they were
    not based on actual cost calculations but arbitrarily set.
    """
    anomalies = []
    round_count = 0
    total = 0

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is None:
            continue
        total += 1
        int_montant = int(montant)
        if int_montant % ROUND_NUMBER_MODULO == 0:
            round_count += 1

    # Only flag if a high proportion of offers are round numbers
    if total >= MIN_SOUMISSIONS_FOR_STATS and round_count / total >= 0.8:
        for soumission in soumissions:
            montant = _safe_decimal(soumission.get("montant_financier"))
            if montant is None:
                continue
            int_montant = int(montant)
            if int_montant % ROUND_NUMBER_MODULO == 0:
                anomalies.append({
                    "id_soumission": int(soumission["id_soumission"]),
                    "type_anomalie": "BIAIS_NOMBRES_RONDS",
                    "niveau_severite": "FAIBLE",
                    "score_confiance": CONFIDENCE_WEIGHTS["BIAIS_NOMBRES_RONDS"],
                    "details": (
                        f"Montant parfaitement arrondi ({montant:,.2f} DA). "
                        f"{round_count}/{total} offres utilisent des nombres ronds, "
                        f"ce qui est inhabituel pour des offres basées sur des calculs réels."
                    ),
                })

    return anomalies


def _detect_bid_rotation(soumissions: List[Dict], historical_wins: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Detect bid rotation patterns by analyzing historical winning patterns.
    In bid rotation, colluding operators take turns being the lowest bidder.
    
    historical_wins format:
    [
        {"id_appel_offre": 1, "id_soumissionnaire": 10, "id_soumission": 100},
        {"id_appel_offre": 2, "id_soumissionnaire": 20, "id_soumission": 200},
        ...
    ]
    """
    anomalies = []
    if not historical_wins or len(historical_wins) < 3:
        return anomalies

    # Count wins per operator
    win_counts: Counter = Counter()
    operator_ids: set = set()
    for win in historical_wins:
        op_id = win.get("id_soumissionnaire")
        if op_id is not None:
            win_counts[op_id] += 1
            operator_ids.add(op_id)

    # Check for rotation pattern: wins are evenly distributed
    if len(win_counts) < 2:
        return anomalies

    counts = list(win_counts.values())
    avg_wins = sum(counts) / len(counts)
    max_deviation = max(abs(c - avg_wins) for c in counts)

    # If wins are suspiciously evenly distributed
    if avg_wins > 0 and max_deviation / avg_wins < Decimal("0.3"):
        rotating_operators = list(win_counts.keys())
        for soumission in soumissions:
            op_id = soumission.get("id_soumissionnaire")
            if op_id in rotating_operators:
                anomalies.append({
                    "id_soumission": int(soumission["id_soumission"]),
                    "type_anomalie": "ROTATION_SOUMISSIONNAIRES",
                    "niveau_severite": "MOYEN",
                    "score_confiance": CONFIDENCE_WEIGHTS["ROTATION_SOUMISSIONNAIRES"],
                    "details": (
                        f"Schéma de rotation détecté. L'opérateur #{op_id} fait partie "
                        f"d'un groupe de {len(rotating_operators)} opérateurs qui se "
                        f"partagent les marchés de façon suspecte. "
                        f"Distribution des victoires: {dict(win_counts)}."
                    ),
                    "soumissions_impliquees": [
                        int(s["id_soumission"]) for s in soumissions
                        if s.get("id_soumissionnaire") in rotating_operators
                    ],
                })

    return anomalies


# ---------------------------------------------------------------------------
# Main detection orchestrator
# ---------------------------------------------------------------------------
def detect_price_and_similarity_anomalies(
    soumissions: List[Dict],
    montant_estime: Optional[Decimal] = None,
    historical_wins: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Main anomaly detection engine. Runs all detection algorithms and 
    returns a consolidated list of detected anomalies.
    
    Parameters:
    -----------
    soumissions : list of dict
        Each dict must contain at minimum:
        - id_soumission: int
        - montant_financier: str/Decimal
        Optional:
        - signature_document: str (hash of technical docs)
        - id_soumissionnaire: int (operator ID)
    
    montant_estime : Decimal, optional
        The estimated budget for the tender (montant_estime from appel_offre).
        Used for relative anomaly scoring.
    
    historical_wins : list of dict, optional
        Historical winning data for bid rotation analysis.
    
    Returns:
    --------
    list of dict, each containing:
        - id_soumission
        - type_anomalie
        - niveau_severite
        - score_confiance
        - details
        - soumissions_impliquees (optional)
    """
    if not soumissions:
        return []

    anomalies: List[Dict] = []

    # Extract valid financial amounts
    montants: List[Decimal] = []
    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is not None:
            montants.append(montant)

    moyenne = sum(montants) / len(montants) if montants else None

    # 1. Document similarity detection
    anomalies.extend(_detect_document_similarity(soumissions))

    # 2. Price similarity to mean
    if moyenne is not None:
        anomalies.extend(_detect_price_similarity_to_mean(soumissions, montants, moyenne))

    # 3. Pairwise price proximity (bilateral collusion)
    anomalies.extend(_detect_pairwise_price_proximity(soumissions))

    # 4. Low dispersion detection (coordinated pricing)
    anomalies.extend(_detect_low_dispersion(montants, soumissions))

    # 5. Statistical outliers (Z-Score + IQR)
    if moyenne is not None:
        anomalies.extend(_detect_statistical_outliers(soumissions, montants, moyenne))

    # 6. Complementary bidding (cover bids)
    anomalies.extend(_detect_complementary_bids(soumissions, montant_estime))

    # 7. Round number bias
    anomalies.extend(_detect_round_number_bias(soumissions))

    # 8. Bid rotation analysis (requires historical data)
    if historical_wins:
        anomalies.extend(_detect_bid_rotation(soumissions, historical_wins))

    # Deduplicate: if both SIMILARITE_PRIX and COLLUSION_CLUSTER_PRIX 
    # are reported for the same soumission, keep the higher-confidence one
    anomalies = _deduplicate_anomalies(anomalies)

    logger.info(
        "Anomaly detection completed: %d anomalies found across %d soumissions",
        len(anomalies),
        len(soumissions),
    )

    return anomalies


def _deduplicate_anomalies(anomalies: List[Dict]) -> List[Dict]:
    """
    Remove lower-priority duplicates when multiple rules flag the same
    soumission for overlapping reasons.
    """
    # Group by (id_soumission, type_anomalie)
    seen: Dict[Tuple[int, str], Dict] = {}
    for anomaly in anomalies:
        key = (anomaly["id_soumission"], anomaly["type_anomalie"])
        existing = seen.get(key)
        if existing is None:
            seen[key] = anomaly
        else:
            # Keep the one with higher confidence
            if anomaly["score_confiance"] > existing["score_confiance"]:
                seen[key] = anomaly

    return list(seen.values())


# ---------------------------------------------------------------------------
# Summary report generator
# ---------------------------------------------------------------------------
def generate_anomaly_summary(anomalies: List[Dict], soumissions_count: int) -> Dict[str, Any]:
    """
    Generate a summary report of all detected anomalies for a given
    appel d'offres. Useful for dashboard display.
    """
    by_type: Dict[str, int] = defaultdict(int)
    by_severity: Dict[str, int] = defaultdict(int)
    affected_soumissions: set = set()

    for a in anomalies:
        by_type[a["type_anomalie"]] += 1
        by_severity[a["niveau_severite"]] += 1
        affected_soumissions.add(a["id_soumission"])

    # Calculate overall risk score (0-100)
    severity_weights = {"ELEVEE": 3, "MOYEN": 2, "FAIBLE": 1}
    weighted_score = sum(
        severity_weights.get(a["niveau_severite"], 1) * float(a["score_confiance"])
        for a in anomalies
    )
    max_possible = soumissions_count * 3 * 1.0 if soumissions_count > 0 else 1
    risk_score = min(100, int((weighted_score / max_possible) * 100))

    # Determine risk level
    if risk_score >= 70:
        risk_level = "CRITIQUE"
    elif risk_score >= 40:
        risk_level = "ELEVE"
    elif risk_score >= 20:
        risk_level = "MOYEN"
    else:
        risk_level = "FAIBLE"

    return {
        "total_anomalies": len(anomalies),
        "soumissions_analysees": soumissions_count,
        "soumissions_affectees": len(affected_soumissions),
        "repartition_par_type": dict(by_type),
        "repartition_par_severite": dict(by_severity),
        "score_risque_global": risk_score,
        "niveau_risque": risk_level,
        "recommandation": _get_recommendation(risk_level),
    }


def _get_recommendation(risk_level: str) -> str:
    """Return an actionable recommendation based on risk level."""
    recommendations = {
        "CRITIQUE": (
            "ALERTE CRITIQUE: Fortes suspicions de collusion détectées. "
            "Il est recommandé de saisir la Commission des Marchés Publics "
            "et d'envisager l'annulation de la procédure conformément à "
            "l'article 55 de la Loi 23-12."
        ),
        "ELEVE": (
            "ALERTE ÉLEVÉE: Anomalies significatives détectées. "
            "Un examen approfondi par la Commission d'Évaluation est "
            "nécessaire avant toute attribution. Documenter les vérifications "
            "effectuées dans le procès-verbal."
        ),
        "MOYEN": (
            "ALERTE MODÉRÉE: Quelques indicateurs suspects relevés. "
            "La Commission d'Évaluation devrait examiner les offres "
            "concernées avec une attention particulière lors de "
            "l'évaluation technique et financière."
        ),
        "FAIBLE": (
            "Aucune anomalie critique détectée. Les offres semblent "
            "refléter une concurrence saine. Procéder à l'évaluation "
            "normale conformément à la Loi 23-12."
        ),
    }
    return recommendations.get(risk_level, recommendations["FAIBLE"])