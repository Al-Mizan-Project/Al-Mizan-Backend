"""
Saucissonnage (Market Splitting) Detection Engine.
====================================================

CONTEXTE MÉTIER
---------------
Le « saucissonnage » consiste, pour un service contractant, à fractionner
artificiellement un besoin unique en plusieurs petits marchés afin de rester
sous les seuils réglementaires qui imposeraient une procédure plus rigoureuse
(p.ex. éviter un appel d'offres ouvert en émettant 3 consultations).

Cette pratique est explicitement interdite par l'**Article 7 de la Loi 23-12** :

    « Il est interdit de scinder les besoins à l'effet de les soustraire
      aux procédures... aux seuils fixés par voie réglementaire. »

OBJECTIF DU MODULE
------------------
Fournir une fonction pure ``detect_saucissonnage(appels, service_contractant_id=None)``
qui prend une liste d'appels d'offres (sous forme de dicts) et renvoie :

    {
        "anomalies": [...],   # liste plate d'anomalies détectées
        "summary":   {...},   # synthèse + score de risque + recommandation
    }

Le module est **pur Python** (pas de dépendance Django/DRF). Il est appelé
depuis ``ia_service/views.py`` (endpoints ``/ia/saucissonnage/detecter`` et
``/ia/saucissonnage/detecter-auto``) et peut aussi être appelé depuis un job
Celery, un script de batch ou des tests unitaires.

ALGORITHMES IMPLÉMENTÉS (4 signaux indépendants)
------------------------------------------------
1. **Proximité de seuil**       — un appel dont le montant est juste sous un
   seuil (≥ 85 % du seuil applicable selon le type_prestation).
2. **Clustering temporel**      — plusieurs appels similaires d'un même
   service contractant publiés dans une fenêtre courte (90 j).
3. **Cumul dépassant un seuil** — N appels chacun sous le seuil mais dont la
   somme dépasse le seuil applicable (signal le plus fort = saucissonnage avéré).
4. **Même fournisseur**         — un même attributaire remporte plusieurs
   marchés du même service contractant (collusion possible côté demande).

ARCHITECTURE INTERNE
--------------------
- Section 1 : constantes (seuils, fenêtres temporelles, ratios).
- Section 2 : helpers (normalisation texte, parsing montants/dates, similarité).
- Section 3 : primitive de **clustering déterministe** (union-find) qui
  regroupe les appels d'un même service contractant ayant le même
  ``type_prestation`` et un sujet sémantiquement proche, dans une fenêtre
  d'un an. C'est la base partagée par les détecteurs 2 et 3.
- Section 4 : les 4 détecteurs (purs : ils prennent des dicts et renvoient
  des anomalies, sans toucher à la base).
- Section 5 : orchestrateur, dédoublonnage, génération du résumé et
  recommandation textuelle.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# 1. CONSTANTES
# =============================================================================
# Seuils réglementaires de la Loi 23-12 (en DZD).
# Au-dessus de ces seuils, des procédures plus contraignantes sont imposées,
# c'est donc PRÉCISÉMENT ces lignes que les fraudeurs essaient de ne pas
# franchir en saucissonnant.
SEUILS_APPEL_OFFRES = {
    "fournitures_services": Decimal("12000000"),
    "travaux":              Decimal("25000000"),
}
SEUILS_CONSULTATION = {
    "consultation_simple_fournitures": Decimal("6000000"),
    "consultation_simple_travaux":     Decimal("15000000"),
}
# Vue agrégée pour compatibilité ascendante (anciens callers / tests).
SEUILS_REGLEMENTAIRES: Dict[str, Decimal] = {**SEUILS_APPEL_OFFRES, **SEUILS_CONSULTATION}

# Fenêtres d'analyse
TEMPORAL_WINDOW_DAYS = 90    # cluster temporel rapproché (signal #2)
ANNUAL_WINDOW_DAYS   = 365   # fenêtre annuelle pour le cumul (signal #3)

# Seuils de déclenchement
THRESHOLD_PROXIMITY_RATIO   = Decimal("0.85")  # signal #1 : ≥ 85 % du seuil
SIMILARITY_THRESHOLD        = 0.30             # Jaccard mini pour clusterer
MIN_CONTRACTS_FOR_DETECTION = 2                # nb mini d'appels pour cluster
MIN_VENDOR_REPETITION       = 3                # nb mini pour signal #4

# Mots vides FR + termes trop génériques en marchés publics
STOP_WORDS_FR: Set[str] = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "en",
    "a", "au", "aux", "ce", "ces", "cette", "pour", "par", "sur", "dans",
    "avec", "son", "sa", "ses", "nos", "vos", "leur", "leurs", "qui", "que",
    "dont", "est", "sont", "sera", "seront", "ete", "etre",
    # bruit du domaine
    "marche", "public", "contrat", "acquisition", "fourniture", "prestation",
    "lot", "tranche", "phase",
}


# =============================================================================
# 2. HELPERS
# =============================================================================
def _normalize_text(text: Any) -> str:
    """Minuscules + suppression accents + suppression ponctuation."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_keywords(text: Any) -> Set[str]:
    """Tokens significatifs (>2 lettres, hors stop-words)."""
    return {
        w for w in _normalize_text(text).split()
        if len(w) > 2 and w not in STOP_WORDS_FR
    }


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _safe_decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_date(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    raw = str(value)[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _appel_id(appel: Dict) -> Any:
    """Tolère les deux conventions de nommage de la PK."""
    return appel.get("id_appel_offre") or appel.get("id_appel_offres")


def _normalized_type_prestation(appel: Dict) -> str:
    """Renvoie 'travaux' | 'fournitures_services' | 'inconnu'."""
    tp = str(appel.get("type_prestation", "")).strip().lower()
    if tp == "travaux":
        return "travaux"
    if tp in {"fournitures", "services", "etudes"}:
        return "fournitures_services"
    return "inconnu"


def _threshold_for_appel(appel: Dict) -> List[Tuple[str, Decimal]]:
    """
    Renvoie la liste des seuils applicables à *cet* appel.
    Si le ``type_prestation`` est connu, on ne renvoie QUE les seuils pertinents
    (évite les faux positifs où un appel travaux serait comparé au seuil
    fournitures). En fallback (type inconnu), on renvoie tous les seuils
    pour préserver l'ancien comportement.
    """
    kind = _normalized_type_prestation(appel)
    if kind == "travaux":
        return [
            ("consultation_simple_travaux", SEUILS_CONSULTATION["consultation_simple_travaux"]),
            ("travaux",                     SEUILS_APPEL_OFFRES["travaux"]),
        ]
    if kind == "fournitures_services":
        return [
            ("consultation_simple_fournitures", SEUILS_CONSULTATION["consultation_simple_fournitures"]),
            ("fournitures_services",            SEUILS_APPEL_OFFRES["fournitures_services"]),
        ]
    return list(SEUILS_REGLEMENTAIRES.items())


# =============================================================================
# 3. CLUSTERING DÉTERMINISTE (Union-Find)
# =============================================================================
# Un « cluster » = ensemble d'appels d'un même service contractant qui
# partagent (a) le même type_prestation, (b) un sujet sémantiquement proche
# (Jaccard >= SIMILARITY_THRESHOLD), (c) une fenêtre temporelle d'un an.
#
# Pourquoi union-find plutôt que first-fit ?
#   - First-fit dépend de l'ordre d'itération et "absorbe" des appels en
#     élargissant continuellement le set de mots-clés (drift).
#   - Union-find sur un graphe d'arêtes (similarity >= seuil) donne des
#     composantes connexes stables et explicables.
# -----------------------------------------------------------------------------

class _UnionFind:
    """Petit DSU pour grouper des indices d'appels."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _cluster_similar_appels(
    appels: List[Dict],
    *,
    window_days: int = ANNUAL_WINDOW_DAYS,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> List[List[Dict]]:
    """
    Regroupe ``appels`` en composantes connexes selon le critère décrit ci-dessus.

    On ne crée une arête entre deux appels (i, j) que si :
      * même ``id_service_contractant``
      * même ``type_prestation`` normalisé (ou les deux 'inconnu')
      * écart de dates <= ``window_days`` (si les deux dates sont disponibles)
      * Jaccard(mots-clés_i, mots-clés_j) >= ``similarity_threshold``

    Renvoie la liste des clusters de taille >= MIN_CONTRACTS_FOR_DETECTION.
    """
    n = len(appels)
    if n < MIN_CONTRACTS_FOR_DETECTION:
        return []

    # Pré-calculs
    keywords:  List[Set[str]]            = []
    services:  List[Optional[int]]       = []
    types:     List[str]                 = []
    dates:     List[Optional[datetime]]  = []
    for a in appels:
        keywords.append(_extract_keywords(f"{a.get('titre', '')} {a.get('description', '')}"))
        sid = a.get("id_service_contractant")
        services.append(int(sid) if sid is not None else None)
        types.append(_normalized_type_prestation(a))
        dates.append(_parse_date(a.get("date_publication")))

    uf = _UnionFind(n)
    for i in range(n):
        if services[i] is None or not keywords[i]:
            continue
        for j in range(i + 1, n):
            if services[j] != services[i]:
                continue
            if types[i] != types[j]:
                continue
            if dates[i] and dates[j]:
                if abs((dates[i] - dates[j]).days) > window_days:
                    continue
            sim = _jaccard_similarity(keywords[i], keywords[j])
            if sim >= similarity_threshold:
                uf.union(i, j)

    # Reconstruire les clusters
    buckets: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        if services[i] is None or not keywords[i]:
            continue
        buckets[uf.find(i)].append(i)

    return [
        [appels[i] for i in idx_list]
        for idx_list in buckets.values()
        if len(idx_list) >= MIN_CONTRACTS_FOR_DETECTION
    ]


# =============================================================================
# 4. DÉTECTEURS
# =============================================================================
# Chaque détecteur est une fonction PURE (List[Dict] -> List[Dict]).
# Aucun ne touche à la base de données ; ils renvoient juste des anomalies
# que l'orchestrateur dédoublonne et que la vue persiste.
# -----------------------------------------------------------------------------

def _detect_threshold_proximity(appels: List[Dict]) -> List[Dict]:
    """
    Signal #1 — Un appel dont le montant estimé est anormalement proche d'un
    seuil applicable (entre 85 % et 100 % du seuil). C'est l'indice qu'on a
    « rogné » le besoin pour rester sous le seuil.
    """
    anomalies: List[Dict] = []
    for appel in appels:
        montant = _safe_decimal(appel.get("montant_estime"))
        if montant is None or montant <= 0:
            continue

        type_procedure = str(appel.get("type_procedure", "")).lower()
        type_prestation = str(appel.get("type_prestation", "")).lower()
        visibilite     = str(appel.get("visibilite", "")).lower()
        localisation   = appel.get("localisation") or appel.get("wilaya") or "non renseignee"
        aid            = _appel_id(appel)

        for threshold_name, threshold_value in _threshold_for_appel(appel):
            ratio = montant / threshold_value
            if THRESHOLD_PROXIMITY_RATIO <= ratio < Decimal("1.0"):
                anomalies.append({
                    "id_appel_offre": aid,
                    "type_anomalie": "SAUCISSONNAGE_PROXIMITE_SEUIL",
                    "niveau_severite": "MOYEN",
                    "score_confiance": Decimal("0.70"),
                    "details": (
                        f"Montant estimé ({montant:,.2f} DA) anormalement proche "
                        f"du seuil réglementaire '{threshold_name}' "
                        f"({threshold_value:,.2f} DA). Ratio: {ratio * 100:.1f}%. "
                        f"Procédure utilisée: '{type_procedure}'. "
                        f"Type prestation: '{type_prestation or 'inconnu'}'. "
                        f"Visibilité: '{visibilite or 'inconnue'}'. "
                        f"Localisation: '{localisation}'. "
                        f"Vérifier que le besoin n'a pas été artificiellement réduit."
                    ),
                })
                # Ne pas re-flagger le même appel pour les autres seuils du
                # même type ; seul le plus pertinent suffit.
                break

    return anomalies


def _detect_temporal_clustering(appels: List[Dict]) -> List[Dict]:
    """
    Signal #2 — Plusieurs appels similaires d'un même service contractant
    publiés en moins de ``TEMPORAL_WINDOW_DAYS`` jours.

    On part des clusters annuels puis on filtre ceux dont la fenêtre
    temporelle (max - min) tient dans ``TEMPORAL_WINDOW_DAYS``. Une seule
    anomalie est produite par appel impliqué (pas une par paire).
    """
    anomalies: List[Dict] = []
    clusters = _cluster_similar_appels(appels)

    for cluster in clusters:
        dated = [(_parse_date(a.get("date_publication")), a) for a in cluster]
        dated = [(d, a) for d, a in dated if d is not None]
        if len(dated) < MIN_CONTRACTS_FOR_DETECTION:
            continue
        span = (max(d for d, _ in dated) - min(d for d, _ in dated)).days
        if span > TEMPORAL_WINDOW_DAYS:
            continue

        service_id   = cluster[0].get("id_service_contractant")
        cluster_ids  = [_appel_id(a) for a in cluster]
        total_montant = sum(
            (_safe_decimal(a.get("montant_estime")) or Decimal("0")) for a in cluster
        )

        for appel in cluster:
            anomalies.append({
                "id_appel_offre": _appel_id(appel),
                "type_anomalie": "SAUCISSONNAGE_TEMPOREL",
                "niveau_severite": "ELEVEE",
                "score_confiance": Decimal("0.85"),
                "details": (
                    f"Cluster temporel détecté: {len(cluster)} appels d'offres "
                    f"similaires du service contractant #{service_id} "
                    f"publiés sur {span} jours (≤ {TEMPORAL_WINDOW_DAYS}). "
                    f"Montant cumulé: {total_montant:,.2f} DA. "
                    f"Appels concernés: {cluster_ids}."
                ),
                "appels_impliques": cluster_ids,
            })

    return anomalies


def _detect_cumulative_threshold_breach(appels: List[Dict]) -> List[Dict]:
    """
    Signal #3 — **Cœur du saucissonnage**.

    Pour chaque cluster annuel d'appels similaires d'un même service
    contractant et de même ``type_prestation`` :
      * si chaque montant individuel est sous un seuil applicable
      * et que la somme des montants dépasse ce même seuil
    => violation probable de l'Article 7 de la Loi 23-12.
    """
    anomalies: List[Dict] = []
    clusters = _cluster_similar_appels(appels)

    for cluster in clusters:
        montants = [m for m in (_safe_decimal(a.get("montant_estime")) for a in cluster) if m]
        if len(montants) < MIN_CONTRACTS_FOR_DETECTION:
            continue

        total = sum(montants, Decimal("0"))
        # Tous les appels du cluster ont le même type_prestation grâce à
        # _cluster_similar_appels, donc on peut se baser sur le premier.
        applicable_thresholds = _threshold_for_appel(cluster[0])

        for threshold_name, threshold_value in applicable_thresholds:
            all_below       = all(m < threshold_value for m in montants)
            cumulative_over = total >= threshold_value
            if not (all_below and cumulative_over):
                continue

            service_id  = cluster[0].get("id_service_contractant")
            cluster_ids = [_appel_id(a) for a in cluster]
            for appel in cluster:
                anomalies.append({
                    "id_appel_offre": _appel_id(appel),
                    "type_anomalie": "SAUCISSONNAGE_CUMUL_SEUIL",
                    "niveau_severite": "CRITIQUE",
                    "score_confiance": Decimal("0.95"),
                    "details": (
                        f"SAUCISSONNAGE DÉTECTÉ: {len(cluster)} marchés similaires "
                        f"du service contractant #{service_id} sont chacun en "
                        f"dessous du seuil '{threshold_name}' "
                        f"({threshold_value:,.2f} DA), mais leur montant cumulé "
                        f"({total:,.2f} DA) dépasse ce seuil. "
                        f"Montants individuels: "
                        f"{[f'{m:,.2f}' for m in montants]}. "
                        f"Violation probable de l'Article 7 de la Loi 23-12."
                    ),
                    "appels_impliques": cluster_ids,
                })
            # Une seule anomalie par cluster, sur le seuil le plus bas qui matche.
            break

    return anomalies


def _detect_same_vendor_splitting(appels: List[Dict]) -> List[Dict]:
    """
    Signal #4 — Le même opérateur économique remporte plusieurs marchés du
    même service contractant. Suppose que l'attributaire est connu via le
    champ ``id_attributaire`` (souvent fourni en post-attribution).
    """
    anomalies: List[Dict] = []
    by_pair: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
    for appel in appels:
        sid = appel.get("id_service_contractant")
        vid = appel.get("id_attributaire")
        if sid is None or vid is None:
            continue
        try:
            by_pair[(int(sid), int(vid))].append(appel)
        except (TypeError, ValueError):
            continue

    for (service_id, vendor_id), vendor_appels in by_pair.items():
        if len(vendor_appels) < MIN_VENDOR_REPETITION:
            continue
        total = sum(
            (_safe_decimal(a.get("montant_estime")) or Decimal("0"))
            for a in vendor_appels
        )
        group_ids = [_appel_id(a) for a in vendor_appels]
        for appel in vendor_appels:
            anomalies.append({
                "id_appel_offre": _appel_id(appel),
                "type_anomalie": "SAUCISSONNAGE_MEME_FOURNISSEUR",
                "niveau_severite": "ELEVEE",
                "score_confiance": Decimal("0.80"),
                "details": (
                    f"L'opérateur économique #{vendor_id} a obtenu "
                    f"{len(vendor_appels)} marchés du même service contractant "
                    f"(#{service_id}). Montant cumulé: {total:,.2f} DA. "
                    f"Appels concernés: {group_ids}."
                ),
                "appels_impliques": group_ids,
            })

    return anomalies


# =============================================================================
# 5. ORCHESTRATEUR + RÉSUMÉ
# =============================================================================
def detect_saucissonnage(
    appels: List[Dict],
    service_contractant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Point d'entrée principal du module.

    Parameters
    ----------
    appels : list[dict]
        Liste d'appels d'offres. Chaque dict peut contenir :
          - id_appel_offre / id_appel_offres
          - id_service_contractant
          - titre, description
          - montant_estime (Decimal/str)
          - date_publication (datetime/str)
          - type_procedure, type_prestation
          - visibilite, wilaya/localisation
          - id_attributaire (optionnel, signal #4)

    service_contractant_id : int, optional
        Si fourni, n'analyse que les appels de ce service.

    Returns
    -------
    dict
        ``{"anomalies": [...], "summary": {...}}``
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
                "appels_affectes": 0,
                "repartition_par_type": {},
                "repartition_par_severite": {},
                "score_risque_saucissonnage": 0,
                "niveau_risque": "AUCUN",
                "recommandation": _get_saucissonnage_recommendation("AUCUN"),
            },
        }

    all_anomalies: List[Dict] = []
    all_anomalies.extend(_detect_threshold_proximity(appels))
    all_anomalies.extend(_detect_temporal_clustering(appels))
    all_anomalies.extend(_detect_cumulative_threshold_breach(appels))
    all_anomalies.extend(_detect_same_vendor_splitting(appels))

    all_anomalies = _deduplicate_saucissonnage_anomalies(all_anomalies)
    summary = _generate_saucissonnage_summary(all_anomalies, len(appels))

    logger.info(
        "Saucissonnage analysis completed: %d anomalies across %d appels (risk=%s)",
        len(all_anomalies), len(appels), summary["niveau_risque"],
    )
    return {"anomalies": all_anomalies, "summary": summary}


def _deduplicate_saucissonnage_anomalies(anomalies: Iterable[Dict]) -> List[Dict]:
    """Garde la meilleure (score le plus élevé) anomalie par (appel, type)."""
    seen: Dict[Tuple, Dict] = {}
    for anomaly in anomalies:
        key = (anomaly.get("id_appel_offre"), anomaly["type_anomalie"])
        existing = seen.get(key)
        if existing is None or anomaly["score_confiance"] > existing["score_confiance"]:
            seen[key] = anomaly
    return list(seen.values())


# Pondération de gravité utilisée pour le score de risque global.
_SEVERITY_WEIGHTS = {"CRITIQUE": 4, "ELEVEE": 3, "MOYEN": 2, "FAIBLE": 1}


def _generate_saucissonnage_summary(
    anomalies: List[Dict],
    appels_count: int,
) -> Dict[str, Any]:
    """
    Construit la synthèse + le score de risque (0-100).

    Le score est calculé sur la base de la pire anomalie par appel :
        score = (somme des poids max par appel) / (appels_count * poids_max) * 100
    Ce calcul reflète mieux la réalité (un même appel peut être touché par
    plusieurs détecteurs, mais on ne le compte qu'une fois au pire niveau).
    """
    by_type: Dict[str, int] = defaultdict(int)
    by_severity: Dict[str, int] = defaultdict(int)
    worst_per_appel: Dict[Any, int] = {}

    for a in anomalies:
        by_type[a["type_anomalie"]] += 1
        by_severity[a["niveau_severite"]] += 1
        aid = a.get("id_appel_offre")
        weight = _SEVERITY_WEIGHTS.get(a["niveau_severite"], 1)
        if aid is not None and weight > worst_per_appel.get(aid, 0):
            worst_per_appel[aid] = weight

    affected_appels = set(worst_per_appel.keys())
    has_cumul    = by_type.get("SAUCISSONNAGE_CUMUL_SEUIL", 0) > 0
    has_temporal = by_type.get("SAUCISSONNAGE_TEMPOREL", 0) > 0

    if appels_count > 0:
        max_possible = appels_count * max(_SEVERITY_WEIGHTS.values())
        risk_score = int(sum(worst_per_appel.values()) / max_possible * 100)
    else:
        risk_score = 0

    if has_cumul:
        risk_level = "CRITIQUE"
        risk_score = max(risk_score, 80)
    elif has_temporal and len(affected_appels) > 3:
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
        "score_risque_saucissonnage": min(100, risk_score),
        "niveau_risque": risk_level,
        "recommandation": _get_saucissonnage_recommendation(risk_level),
    }


def _get_saucissonnage_recommendation(risk_level: str) -> str:
    """Recommandation actionnable selon le niveau de risque."""
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
