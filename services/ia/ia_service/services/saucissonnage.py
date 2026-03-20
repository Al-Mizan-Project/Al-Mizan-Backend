"""
Saucissonnage (Market Splitting) Detection Engine.

"Saucissonnage" is a practice where a service contractant (contracting authority)
artificially splits a single procurement need into multiple smaller contracts
to stay below regulatory thresholds that would require more rigorous 
procurement procedures (e.g., avoiding an open tender by splitting into 
multiple "gré à gré" or restricted contracts).

This is explicitly prohibited by Article 7 of Loi 23-12 which states:
"Il est interdit de scinder les besoins à l'effet de les soustraire aux 
procédures... les seuils fixés par voie réglementaire."

Detection algorithms:
- Temporal clustering: Similar contracts awarded in rapid succession
- Amount threshold analysis: Multiple contracts just below thresholds
- Subject similarity: Contracts with similar descriptions from same entity
- Vendor analysis: Same vendor receiving multiple small contracts
- Cumulative threshold analysis: Sum of related contracts exceeds thresholds
"""
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regulatory thresholds from Loi 23-12 (in DZD - Algerian Dinar)
# These are the thresholds above which specific procedures are mandatory
# ---------------------------------------------------------------------------
SEUILS_REGLEMENTAIRES = {
    # Fournitures & services — Seuil appel d'offres
    "fournitures_services": Decimal("12_000_000"),
    # Travaux — Seuil appel d'offres  
    "travaux": Decimal("25_000_000"),
    # Consultation simple
    "consultation_simple_fournitures": Decimal("6_000_000"),
    "consultation_simple_travaux": Decimal("15_000_000"),
}

# Analysis windows
TEMPORAL_WINDOW_DAYS = 90         # 3 months window for temporal clustering
ANNUAL_WINDOW_DAYS = 365          # 1 year for cumulative analysis
THRESHOLD_PROXIMITY_RATIO = Decimal("0.85")  # Flag if amount > 85% of threshold
MIN_CONTRACTS_FOR_DETECTION = 2   # Minimum contracts to suspect splitting

# Text similarity
STOP_WORDS_FR = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "en",
    "a", "au", "aux", "ce", "ces", "cette", "pour", "par", "sur", "dans",
    "avec", "son", "sa", "ses", "nos", "vos", "leur", "leurs", "qui", "que",
    "dont", "est", "sont", "sera", "seront", "été", "être",
    "marche", "public", "contrat", "acquisition", "fourniture", "prestation",
}


# ---------------------------------------------------------------------------
# Text processing utilities
# ---------------------------------------------------------------------------
def _normalize_text(text: str) -> str:
    """Normalize text for comparison: remove accents, lowercase, strip."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_keywords(text: str) -> Set[str]:
    """Extract meaningful keywords from text, ignoring stop words."""
    normalized = _normalize_text(text)
    words = normalized.split()
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS_FR}


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _safe_decimal(value) -> Optional[Decimal]:
    """Safely convert a value to Decimal."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_date(value) -> Optional[datetime]:
    """Parse a date from string or datetime."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Detection algorithms
# ---------------------------------------------------------------------------
def _detect_threshold_proximity(appels: List[Dict]) -> List[Dict]:
    """
    Detect contracts whose amounts are suspiciously close to regulatory 
    thresholds — a sign that the amount was deliberately kept below 
    the threshold to avoid stricter procurement procedures.
    """
    anomalies = []

    for appel in appels:
        montant = _safe_decimal(appel.get("montant_estime"))
        if montant is None or montant <= 0:
            continue

        type_procedure = str(appel.get("type_procedure", "")).lower()
        id_appel = appel.get("id_appel_offre") or appel.get("id_appel_offres")

        for threshold_name, threshold_value in SEUILS_REGLEMENTAIRES.items():
            ratio = montant / threshold_value
            if THRESHOLD_PROXIMITY_RATIO <= ratio < Decimal("1.0"):
                anomalies.append({
                    "id_appel_offre": id_appel,
                    "type_anomalie": "SAUCISSONNAGE_PROXIMITE_SEUIL",
                    "niveau_severite": "MOYEN",
                    "score_confiance": Decimal("0.70"),
                    "details": (
                        f"Montant estimé ({montant:,.2f} DA) anormalement proche "
                        f"du seuil réglementaire '{threshold_name}' "
                        f"({threshold_value:,.2f} DA). Ratio: {ratio * 100:.1f}%. "
                        f"Procédure utilisée: '{type_procedure}'. "
                        f"Vérifier que le besoin n'a pas été artificiellement réduit."
                    ),
                })

    return anomalies


def _detect_temporal_clustering(appels: List[Dict], window_days: int = TEMPORAL_WINDOW_DAYS) -> List[Dict]:
    """
    Detect contracts from the same service contractant that are 
    published within a short time window and have similar subjects.
    """
    anomalies = []

    # Group by service contractant
    by_service: Dict[int, List[Dict]] = defaultdict(list)
    for appel in appels:
        service_id = appel.get("id_service_contractant")
        if service_id is not None:
            by_service[int(service_id)].append(appel)

    for service_id, service_appels in by_service.items():
        if len(service_appels) < MIN_CONTRACTS_FOR_DETECTION:
            continue

        # Sort by publication date
        dated_appels = []
        for appel in service_appels:
            date = _parse_date(appel.get("date_publication"))
            if date:
                dated_appels.append((date, appel))
        dated_appels.sort(key=lambda x: x[0])

        # Sliding window analysis
        for i, (date_i, appel_i) in enumerate(dated_appels):
            cluster = [(date_i, appel_i)]
            keywords_i = _extract_keywords(
                f"{appel_i.get('titre', '')} {appel_i.get('description', '')}"
            )

            for j in range(i + 1, len(dated_appels)):
                date_j, appel_j = dated_appels[j]
                if (date_j - date_i).days > window_days:
                    break

                keywords_j = _extract_keywords(
                    f"{appel_j.get('titre', '')} {appel_j.get('description', '')}"
                )
                similarity = _jaccard_similarity(keywords_i, keywords_j)

                if similarity > 0.3:  # 30% keyword overlap
                    cluster.append((date_j, appel_j))

            if len(cluster) >= MIN_CONTRACTS_FOR_DETECTION:
                cluster_ids = [
                    a.get("id_appel_offre") or a.get("id_appel_offres")
                    for _, a in cluster
                ]
                total_montant = sum(
                    _safe_decimal(a.get("montant_estime")) or Decimal("0")
                    for _, a in cluster
                )

                for _, appel in cluster:
                    aid = appel.get("id_appel_offre") or appel.get("id_appel_offres")
                    anomalies.append({
                        "id_appel_offre": aid,
                        "type_anomalie": "SAUCISSONNAGE_TEMPOREL",
                        "niveau_severite": "ELEVEE",
                        "score_confiance": Decimal("0.85"),
                        "details": (
                            f"Cluster temporel détecté: {len(cluster)} appels d'offres "
                            f"similaires du même service contractant (#{service_id}) "
                            f"publiés en moins de {window_days} jours. "
                            f"Montant cumulé: {total_montant:,.2f} DA. "
                            f"Appels concernés: {cluster_ids}."
                        ),
                        "appels_impliques": cluster_ids,
                    })

    return anomalies


def _detect_cumulative_threshold_breach(appels: List[Dict]) -> List[Dict]:
    """
    Detect when multiple smaller contracts from the same service contractant,
    with similar subjects, cumulatively exceed a regulatory threshold.
    This is the core saucissonnage pattern.
    """
    anomalies = []

    # Group by service contractant
    by_service: Dict[int, List[Dict]] = defaultdict(list)
    for appel in appels:
        service_id = appel.get("id_service_contractant")
        if service_id is not None:
            by_service[int(service_id)].append(appel)

    for service_id, service_appels in by_service.items():
        if len(service_appels) < MIN_CONTRACTS_FOR_DETECTION:
            continue

        # Group similar appels by semantic keyword overlap instead of strict exact signature.
        # This catches "lot 1/2/3" naming variants that share the same procurement subject.
        clusters: List[Dict[str, Any]] = []
        for appel in service_appels:
            keywords = _extract_keywords(
                f"{appel.get('titre', '')} {appel.get('description', '')}"
            )
            placed = False
            for cluster in clusters:
                similarity = _jaccard_similarity(keywords, cluster["keywords"])
                if similarity >= 0.3:
                    cluster["appels"].append(appel)
                    cluster["keywords"] = cluster["keywords"] | keywords
                    placed = True
                    break

            if not placed:
                clusters.append({"keywords": keywords, "appels": [appel]})

        subject_groups: Dict[str, List[Dict]] = {
            f"cluster_{idx}": cluster["appels"]
            for idx, cluster in enumerate(clusters)
        }

        for subject_key, group in subject_groups.items():
            if len(group) < MIN_CONTRACTS_FOR_DETECTION:
                continue

            total_montant = Decimal("0")
            individual_montants = []
            for appel in group:
                m = _safe_decimal(appel.get("montant_estime"))
                if m:
                    total_montant += m
                    individual_montants.append(m)

            if not individual_montants:
                continue

            # Check if each individual amount is below a threshold
            # but the cumulative total exceeds it
            for threshold_name, threshold_value in SEUILS_REGLEMENTAIRES.items():
                all_below = all(m < threshold_value for m in individual_montants)
                cumulative_above = total_montant >= threshold_value

                if all_below and cumulative_above:
                    group_ids = [
                        a.get("id_appel_offre") or a.get("id_appel_offres")
                        for a in group
                    ]
                    for appel in group:
                        aid = appel.get("id_appel_offre") or appel.get("id_appel_offres")
                        anomalies.append({
                            "id_appel_offre": aid,
                            "type_anomalie": "SAUCISSONNAGE_CUMUL_SEUIL",
                            "niveau_severite": "CRITIQUE",
                            "score_confiance": Decimal("0.95"),
                            "details": (
                                f"SAUCISSONNAGE DÉTECTÉ: {len(group)} marchés similaires "
                                f"du service contractant #{service_id} sont chacun en "
                                f"dessous du seuil '{threshold_name}' "
                                f"({threshold_value:,.2f} DA), mais leur montant cumulé "
                                f"({total_montant:,.2f} DA) dépasse ce seuil. "
                                f"Montants individuels: "
                                f"{[f'{m:,.2f}' for m in individual_montants]}. "
                                f"Violation probable de l'Article 7 de la Loi 23-12."
                            ),
                            "appels_impliques": group_ids,
                        })

    return anomalies


def _detect_same_vendor_splitting(appels: List[Dict]) -> List[Dict]:
    """
    Detect when the same vendor wins multiple small contracts from 
    the same service contractant — possible coordinated splitting.
    
    Requires 'id_attributaire' (winning vendor) in appel data.
    """
    anomalies = []

    # Group by (service_contractant, attributaire)
    by_pair: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
    for appel in appels:
        service_id = appel.get("id_service_contractant")
        vendor_id = appel.get("id_attributaire")
        if service_id is not None and vendor_id is not None:
            by_pair[(int(service_id), int(vendor_id))].append(appel)

    for (service_id, vendor_id), vendor_appels in by_pair.items():
        if len(vendor_appels) < MIN_CONTRACTS_FOR_DETECTION + 1:
            continue

        total_montant = sum(
            _safe_decimal(a.get("montant_estime")) or Decimal("0")
            for a in vendor_appels
        )
        group_ids = [
            a.get("id_appel_offre") or a.get("id_appel_offres")
            for a in vendor_appels
        ]

        for appel in vendor_appels:
            aid = appel.get("id_appel_offre") or appel.get("id_appel_offres")
            anomalies.append({
                "id_appel_offre": aid,
                "type_anomalie": "SAUCISSONNAGE_MEME_FOURNISSEUR",
                "niveau_severite": "ELEVEE",
                "score_confiance": Decimal("0.80"),
                "details": (
                    f"L'opérateur économique #{vendor_id} a obtenu "
                    f"{len(vendor_appels)} marchés du même service contractant "
                    f"(#{service_id}). Montant cumulé: {total_montant:,.2f} DA. "
                    f"Appels concernés: {group_ids}."
                ),
                "appels_impliques": group_ids,
            })

    return anomalies


# ---------------------------------------------------------------------------
# Main saucissonnage detection orchestrator
# ---------------------------------------------------------------------------
def detect_saucissonnage(
    appels: List[Dict],
    service_contractant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main entry point for saucissonnage detection.
    
    Parameters:
    -----------
    appels : list of dict
        List of appels d'offres to analyze. Each should contain:
        - id_appel_offre / id_appel_offres: int
        - id_service_contractant: int
        - titre: str
        - description: str (optional)
        - montant_estime: Decimal/str
        - date_publication: str/datetime
        - type_procedure: str
        - id_attributaire: int (optional, for vendor analysis)
    
    service_contractant_id : int, optional
        If provided, only analyze appels from this specific service.
    
    Returns:
    --------
    dict with:
        - anomalies: list of detected anomalies
        - summary: analysis summary
    """
    if service_contractant_id is not None:
        appels = [
            a for a in appels
            if a.get("id_service_contractant") == service_contractant_id
        ]

    if not appels:
        return {
            "anomalies": [],
            "summary": {
                "total_anomalies": 0,
                "appels_analyses": 0,
                "score_risque_saucissonnage": 0,
                "niveau_risque": "AUCUN",
            },
        }

    all_anomalies: List[Dict] = []

    # 1. Threshold proximity analysis
    all_anomalies.extend(_detect_threshold_proximity(appels))

    # 2. Temporal clustering analysis
    all_anomalies.extend(_detect_temporal_clustering(appels))

    # 3. Cumulative threshold breach (core saucissonnage)
    all_anomalies.extend(_detect_cumulative_threshold_breach(appels))

    # 4. Same vendor splitting
    all_anomalies.extend(_detect_same_vendor_splitting(appels))

    # Deduplicate
    all_anomalies = _deduplicate_saucissonnage_anomalies(all_anomalies)

    # Generate summary
    summary = _generate_saucissonnage_summary(all_anomalies, len(appels))

    logger.info(
        "Saucissonnage analysis completed: %d anomalies across %d appels",
        len(all_anomalies),
        len(appels),
    )

    return {
        "anomalies": all_anomalies,
        "summary": summary,
    }


def _deduplicate_saucissonnage_anomalies(anomalies: List[Dict]) -> List[Dict]:
    """Remove duplicate anomalies."""
    seen: Dict[Tuple, Dict] = {}
    for anomaly in anomalies:
        key = (anomaly.get("id_appel_offre"), anomaly["type_anomalie"])
        existing = seen.get(key)
        if existing is None:
            seen[key] = anomaly
        elif anomaly["score_confiance"] > existing["score_confiance"]:
            seen[key] = anomaly
    return list(seen.values())


def _generate_saucissonnage_summary(anomalies: List[Dict], appels_count: int) -> Dict[str, Any]:
    """Generate a summary report for saucissonnage analysis."""
    by_type: Dict[str, int] = defaultdict(int)
    by_severity: Dict[str, int] = defaultdict(int)
    affected_appels: set = set()

    for a in anomalies:
        by_type[a["type_anomalie"]] += 1
        by_severity[a["niveau_severite"]] += 1
        if a.get("id_appel_offre"):
            affected_appels.add(a["id_appel_offre"])

    # Critical risk if cumulative threshold breach detected
    has_cumul = by_type.get("SAUCISSONNAGE_CUMUL_SEUIL", 0) > 0
    has_temporal = by_type.get("SAUCISSONNAGE_TEMPOREL", 0) > 0

    severity_weights = {"CRITIQUE": 4, "ELEVEE": 3, "MOYEN": 2, "FAIBLE": 1}
    weighted_score = sum(
        severity_weights.get(a["niveau_severite"], 1) * float(a["score_confiance"])
        for a in anomalies
    )
    max_possible = appels_count * 4 * 1.0 if appels_count > 0 else 1
    risk_score = min(100, int((weighted_score / max_possible) * 100))

    if has_cumul:
        risk_level = "CRITIQUE"
        risk_score = max(risk_score, 80)
    elif has_temporal and len(anomalies) > 3:
        risk_level = "ELEVE"
        risk_score = max(risk_score, 50)
    elif risk_score >= 40:
        risk_level = "ELEVE"
    elif risk_score >= 20:
        risk_level = "MOYEN"
    elif anomalies:
        risk_level = "FAIBLE"
    else:
        risk_level = "AUCUN"

    return {
        "total_anomalies": len(anomalies),
        "appels_analyses": appels_count,
        "appels_affectes": len(affected_appels),
        "repartition_par_type": dict(by_type),
        "repartition_par_severite": dict(by_severity),
        "score_risque_saucissonnage": risk_score,
        "niveau_risque": risk_level,
        "recommandation": _get_saucissonnage_recommendation(risk_level),
    }


def _get_saucissonnage_recommendation(risk_level: str) -> str:
    """Return actionable recommendation for saucissonnage risk."""
    recommendations = {
        "CRITIQUE": (
            "ALERTE CRITIQUE - SAUCISSONNAGE PROBABLE: Des marchés ont été "
            "artificiellement divisés pour contourner les seuils réglementaires. "
            "Conformément à l'Article 7 de la Loi 23-12, il est interdit de "
            "scinder les besoins. Signaler à la Tutelle et à l'Inspection "
            "Générale des Finances. Les marchés concernés doivent être "
            "consolidés en un seul appel d'offres."
        ),
        "ELEVE": (
            "ALERTE ÉLEVÉE: Schéma de fractionnement suspect détecté. "
            "Vérifier auprès du service contractant si ces marchés "
            "correspondent à des besoins réellement distincts. "
            "Exiger une justification écrite conformément à la Loi 23-12."
        ),
        "MOYEN": (
            "ALERTE MODÉRÉE: Certains indicateurs de fractionnement "
            "relevés. Surveiller l'évolution et demander des "
            "clarifications au service contractant sur la justification "
            "économique de la séparation des marchés."
        ),
        "FAIBLE": (
            "Risque faible de saucissonnage. Quelques indicateurs mineurs "
            "détectés. Aucune action immédiate requise, mais maintenir "
            "la surveillance périodique."
        ),
        "AUCUN": (
            "Aucun indicateur de saucissonnage détecté. Les marchés "
            "analysés semblent respecter les seuils réglementaires "
            "de la Loi 23-12."
        ),
    }
    return recommendations.get(risk_level, recommendations["AUCUN"])
