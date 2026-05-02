"""
ia_service/services/redaction.py

Module d'aide à la rédaction des Cahiers des Charges (CDC).
Analyse le texte extrait du CDC en contexte avec les métadonnées de l'appel d'offres
et retourne des suggestions structurées basées sur la Loi 23-12 et la Loi 18-07.

Configuration via settings.py (chargé depuis .env) :
    GEMINI_API_KEY            — clé(s) API Google Gemini.
                                Accepte une seule clé OU une liste séparée par des virgules
                                pour le pool de clés (ex: "key1,key2,key3").
    GEMINI_MODEL              — modèle à utiliser (défaut: gemini-2.0-flash)
    GEMINI_MAX_TOKENS         — tokens max en sortie (défaut: 2000)
    REMOTE_SERVICE_TIMEOUT_IA — timeout HTTP en secondes (défaut: 60)
    GEMINI_MAX_RETRIES        — nombre max de tentatives PAR CLÉ en cas de 429 (défaut: 2)
    GEMINI_RETRY_BASE_DELAY   — délai de base en secondes pour le backoff (défaut: 10)

Pool de clés :
    Avec plusieurs clés, chaque 429 fait basculer vers la clé suivante du pool
    au lieu d'attendre. Le backoff n'est utilisé qu'une fois toutes les clés épuisées
    sur un même tour.

    Exemple .env :
        GEMINI_API_KEY=AIzaSy...clé1,AIzaSy...clé2,AIzaSy...clé3
"""

import json
import logging
import time
from itertools import cycle
from threading import Lock
from typing import List, Optional

from django.conf import settings

from .cdc import revise_cdc_text
from .ocr import extract_document_text
from .integrations import fetch_document_binary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — lue depuis Django settings (settings.py → .env)
# ---------------------------------------------------------------------------

# Pool de clés — initialisé une seule fois au démarrage du processus
_key_pool: List[str] = []
_key_cycle = None
_key_lock = Lock()


def _init_key_pool() -> None:
    """
    Initialise le pool de clés depuis GEMINI_API_KEY.
    Supporte une clé unique ou plusieurs clés séparées par des virgules.
    Appelé au premier accès (lazy init thread-safe).
    """
    global _key_pool, _key_cycle
    raw = getattr(settings, "GEMINI_API_KEY", "") or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    _key_pool = keys
    _key_cycle = cycle(keys) if keys else None
    if len(keys) > 1:
        logger.info("Gemini key pool initialized with %d keys", len(keys))
    elif len(keys) == 1:
        logger.debug("Gemini single key configured")
    else:
        logger.error("No GEMINI_API_KEY configured")


def _get_next_key() -> Optional[str]:
    """Retourne la prochaine clé disponible dans le pool (round-robin)."""
    with _key_lock:
        if _key_cycle is None:
            _init_key_pool()
        if not _key_pool:
            return None
        return next(_key_cycle)


def _get_all_keys() -> List[str]:
    """Retourne toutes les clés du pool (pour itérer sur chacune en cas de 429)."""
    with _key_lock:
        if _key_cycle is None:
            _init_key_pool()
        return list(_key_pool)


def _get_gemini_api_key() -> str:
    """Compatibilité — retourne la première clé du pool."""
    keys = _get_all_keys()
    return keys[0] if keys else ""

def _get_gemini_model() -> str:
    return getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")

def _get_gemini_max_tokens() -> int:
    return int(getattr(settings, "GEMINI_MAX_TOKENS", 2000))

def _get_gemini_api_url() -> str:
    model = _get_gemini_model()
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{model}:generateContent"
    )

def _get_timeout() -> float:
    return float(getattr(settings, "REMOTE_SERVICE_TIMEOUT_IA", 60.0))

def _get_max_retries() -> int:
    """Nombre maximum de tentatives PAR CLÉ en cas de 429."""
    return int(getattr(settings, "GEMINI_MAX_RETRIES", 2))

def _get_retry_base_delay() -> float:
    """Délai de base en secondes pour le backoff exponentiel."""
    return float(getattr(settings, "GEMINI_RETRY_BASE_DELAY", 10.0))

# Seuil en caractères en dessous duquel le CDC est considéré trop court
MIN_CDC_TEXT_LENGTH = 100

# Codes HTTP qui déclenchent un retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# System prompt — ancré dans la Loi 23-12 et la Loi 18-07
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
Tu es un expert juridique et technique en marchés publics algériens, spécialisé dans la Loi n° 23-12
fixant les règles générales relatives aux marchés publics, et dans la Loi 18-07 relative à la
protection des personnes physiques dans le traitement des données à caractère personnel.

Ton rôle est d'analyser un Cahier des Charges (CDC) rédigé par un service contractant et de fournir
des suggestions concrètes pour améliorer sa conformité réglementaire, sa clarté et sa neutralité concurrentielle.

## Règles fondamentales issues de la Loi 23-12 que tu dois appliquer :

### Principes généraux (Art. 5-8)
- Liberté d'accès à la commande publique : le CDC ne doit pas contenir de clauses qui restreignent
  artificiellement la concurrence.
- Égalité de traitement des candidats : les spécifications techniques doivent être accessibles à
  plusieurs fournisseurs, sans référence exclusive à une marque, un brevet ou un fournisseur unique.
- Transparence des procédures : les critères d'évaluation et leur pondération doivent être explicitement
  définis dans le CDC.

### Rédaction des spécifications techniques (Art. 42-44)
- Les spécifications techniques doivent être définies par référence à des normes algériennes ou,
  à défaut, à des normes internationales (ISO, EN, etc.).
- Il est interdit de mentionner une marque commerciale, un brevet, un type ou une origine particulière
  sauf si cela est justifié par l'objet du marché et accompagné de la mention "ou équivalent".
- Les critères de sélection doivent être proportionnels à l'objet du marché.

### Critères d'éligibilité et de qualification (Art. 65-72)
- Les conditions de participation (chiffre d'affaires minimum, expérience, qualifications) doivent
  être proportionnelles au montant et à la nature du marché.
- L'exigence d'un chiffre d'affaires minimum ne doit pas dépasser deux fois la valeur estimée du marché.
- Les références demandées doivent être pertinentes et limitées aux 3-5 dernières années.

### Pondération technique/financière (Art. 78)
- Pour les marchés de travaux et fournitures : le critère financier doit représenter au moins 30%.
- Pour les marchés d'études et services : le critère technique peut être prépondérant (jusqu'à 80%).
- La somme des pondérations doit toujours être égale à 100%.

### Délais (Art. 50-55)
- Appel d'offres ouvert national : délai minimum de 21 jours entre publication et date limite.
- Appel d'offres ouvert international : délai minimum de 40 jours.
- Appel d'offres restreint : délai minimum de 15 jours.

### Protection des données (Loi 18-07)
- Si le CDC implique le traitement de données personnelles, une clause RGPD-like doit être incluse.
- Les données collectées doivent être minimisées et leur durée de conservation précisée.

## Format de réponse OBLIGATOIRE

Tu dois répondre UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ou après, sans backticks.
La structure exacte est :

{
  "score_conformite": <entier entre 0 et 100>,
  "resume_general": "<2-3 phrases de synthèse>",
  "alertes_critiques": [
    {
      "id": "<identifiant unique ex: ALERT_001>",
      "type": "<terme_discriminant|clause_restrictive|critere_disproportionne|donnee_manquante|violation_loi>",
      "niveau": "<critique|attention|info>",
      "extrait": "<phrase ou extrait du CDC concerné, ou 'Non spécifié' si absent>",
      "article_loi": "<article de référence ex: Art. 42 Loi 23-12>",
      "message": "<explication claire du problème>",
      "suggestion": "<reformulation ou action corrective concrète>"
    }
  ],
  "analyse_sections": [
    {
      "section": "<objet_marche|specifications_techniques|criteres_eligibilite|criteres_evaluation|conditions_execution|clauses_administratives|protection_donnees>",
      "statut": "<present_conforme|present_attention|present_non_conforme|absent>",
      "commentaire": "<observation spécifique>"
    }
  ],
  "suggestions_amelioration": [
    {
      "priorite": "<haute|moyenne|faible>",
      "titre": "<titre court>",
      "description": "<description de l'amélioration suggérée>"
    }
  ],
  "needs_human_validation": <true|false>
}
"""


# ---------------------------------------------------------------------------
# Construction du prompt utilisateur avec le contexte de l'appel
# ---------------------------------------------------------------------------

def _build_user_prompt(texte_cdc: str, contexte_appel: dict) -> str:
    """
    Construit le message utilisateur en injectant le contexte de l'appel d'offres
    et le texte extrait du CDC.
    """
    type_procedure = contexte_appel.get("type_procedure", "Non spécifié")
    type_prestation = contexte_appel.get("type_prestation", "Non spécifié")
    montant = contexte_appel.get("montant_estime")
    montant_str = f"{montant:,.2f} DA" if montant else "Non spécifié"
    poids_technique = contexte_appel.get("poids_technique", 50)
    poids_financier = contexte_appel.get("poids_financier", 50)
    wilaya = contexte_appel.get("wilaya", "Non spécifiée")
    qualification = contexte_appel.get("qualification_category", "Non spécifiée")
    experience_min = contexte_appel.get("minimum_experience_years", 0)
    revenue_min = contexte_appel.get("minimum_revenue_da", 0)
    participation_conditions = contexte_appel.get("participation_conditions", [])

    conditions_str = (
        "\n".join(f"  - {c}" for c in participation_conditions)
        if participation_conditions
        else "  Aucune condition spécifiée"
    )

    return f"""
## Contexte de l'Appel d'Offres

- **Type de procédure** : {type_procedure}
- **Type de prestation** : {type_prestation}
- **Montant estimé** : {montant_str}
- **Wilaya** : {wilaya}
- **Pondération technique** : {poids_technique}%
- **Pondération financière** : {poids_financier}%
- **Catégorie de qualification requise** : {qualification}
- **Expérience minimale requise** : {experience_min} an(s)
- **Chiffre d'affaires minimum requis** : {revenue_min:,} DA
- **Conditions de participation déclarées** :
{conditions_str}

## Texte du Cahier des Charges (CDC)

{texte_cdc}

---

Analyse ce CDC en tenant compte du contexte de l'appel d'offres ci-dessus.
Vérifie notamment :
1. La cohérence entre la pondération technique/financière déclarée ({poids_technique}/{poids_financier})
   et les règles de la Loi 23-12 pour ce type de prestation ({type_prestation}).
2. La proportionnalité des critères d'éligibilité par rapport au montant estimé ({montant_str}).
3. L'absence de clauses discriminantes ou restrictives dans le texte du CDC.
4. La présence de toutes les sections obligatoires.
5. La conformité à la protection des données (Loi 18-07) si applicable.

Retourne uniquement le JSON structuré demandé.
"""


# ---------------------------------------------------------------------------
# Calcul du délai de backoff exponentiel avec jitter
# ---------------------------------------------------------------------------

def _compute_retry_delay(attempt: int, retry_after_header: Optional[str] = None) -> float:
    """
    Calcule le délai d'attente avant la prochaine tentative.

    Priorité :
      1. Header Retry-After renvoyé par Gemini (si présent)
      2. Backoff exponentiel : base * 2^attempt  (ex: 10s, 20s, 40s)

    Args:
        attempt:            Numéro de la tentative échouée (0-based).
        retry_after_header: Valeur brute du header HTTP Retry-After (optionnel).

    Returns:
        Nombre de secondes à attendre.
    """
    if retry_after_header:
        try:
            return max(1.0, float(retry_after_header))
        except (ValueError, TypeError):
            pass

    base = _get_retry_base_delay()
    delay = base * (2 ** attempt)          # 10s → 20s → 40s
    return delay


# ---------------------------------------------------------------------------
# Helpers HTTP internes
# ---------------------------------------------------------------------------

def _parse_gemini_response(response_json: dict) -> Optional[dict]:
    """
    Extrait et parse le JSON retourné dans la réponse Gemini.
    Retourne le dict parsé, ou None si vide / invalide.
    """
    candidates = response_json.get("candidates", [])
    if not candidates:
        logger.warning("Gemini returned no candidates")
        return None

    parts = candidates[0].get("content", {}).get("parts", [])
    raw_text = "".join(p.get("text", "") for p in parts).strip()

    if not raw_text:
        logger.warning("Gemini returned empty content")
        return None

    # Nettoyer les éventuels backticks markdown résiduels
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    return json.loads(raw_text)


def _try_single_key(req_module, body: dict, api_key: str, max_retries: int) -> Optional[dict]:
    """
    Tente d'appeler Gemini avec une clé précise.
    Effectue jusqu'à `max_retries` tentatives pour les erreurs transitoires (5xx, timeout).
    Retourne immédiatement None sur 429 pour laisser la main au pool de clés.

    Returns:
        dict   → succès
        None   → 429 (changer de clé) ou échec définitif après retries
        "hard" → erreur non-retryable (4xx hors 429, ConnectionError, JSON invalide)
                 signale qu'il ne sert à rien d'essayer d'autres clés
    """
    url = f"{_get_gemini_api_url()}?key={api_key}"

    for attempt in range(max_retries):
        try:
            logger.debug(
                "Gemini call — clé …%s, tentative %d/%d",
                api_key[-6:], attempt + 1, max_retries
            )
            response = req_module.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=_get_timeout(),
            )

            # --- 429 : rate limit sur cette clé → on remonte pour changer de clé
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                logger.warning(
                    "Rate limit (429) — clé …%s (Retry-After: %s)",
                    api_key[-6:], retry_after or "non fourni"
                )
                return None  # signal "essaie la prochaine clé"

            # --- Erreurs transitoires 5xx → retry avec backoff
            if response.status_code in {500, 502, 503, 504}:
                is_last = attempt >= max_retries - 1
                if is_last:
                    logger.error(
                        "Erreur transitoire %d — clé …%s, retries épuisés",
                        response.status_code, api_key[-6:]
                    )
                    return None
                delay = _compute_retry_delay(attempt)
                logger.warning(
                    "Erreur transitoire %d — clé …%s, retry dans %.1fs...",
                    response.status_code, api_key[-6:], delay
                )
                time.sleep(delay)
                continue

            # --- Autre erreur HTTP non-retryable (400, 401, 403…)
            if not response.ok:
                logger.error(
                    "Gemini HTTP %d (non-retryable) — clé …%s: %s",
                    response.status_code, api_key[-6:], response.text[:200]
                )
                return "hard"  # type: ignore[return-value]

            # --- Succès : parser et retourner
            return _parse_gemini_response(response.json())

        except req_module.exceptions.Timeout:
            is_last = attempt >= max_retries - 1
            if is_last:
                logger.error("Timeout — clé …%s, retries épuisés", api_key[-6:])
                return None
            delay = _compute_retry_delay(attempt)
            logger.warning(
                "Timeout — clé …%s, retry dans %.1fs...", api_key[-6:], delay
            )
            time.sleep(delay)

        except req_module.exceptions.ConnectionError as exc:
            logger.error("Erreur réseau — clé …%s: %s", api_key[-6:], exc)
            return "hard"  # type: ignore[return-value]

        except json.JSONDecodeError as exc:
            logger.warning("JSON invalide — clé …%s: %s", api_key[-6:], exc)
            return "hard"  # type: ignore[return-value]

        except Exception as exc:
            logger.error("Erreur inattendue — clé …%s: %s", api_key[-6:], exc)
            return "hard"  # type: ignore[return-value]

    return None


# ---------------------------------------------------------------------------
# Appel à l'API Google Gemini — pool de clés + retry + backoff
# ---------------------------------------------------------------------------

def _call_llm(user_prompt: str) -> Optional[dict]:
    """
    Appelle l'API Google Gemini en utilisant le pool de clés configuré.

    Stratégie :
      1. Essaie chaque clé du pool l'une après l'autre en cas de 429.
      2. Pour chaque clé : jusqu'à GEMINI_MAX_RETRIES tentatives sur les 5xx/timeout.
      3. Si toutes les clés sont épuisées sur un tour (toutes 429) :
         attend un délai de backoff puis refait un tour (jusqu'à 2 tours max).
      4. Si une erreur "hard" (4xx non-429, réseau, JSON) est détectée : abandon immédiat.

    Avec N clés et GEMINI_MAX_RETRIES=2 :
      - Tentatives max effectives = N × 2 × 2 tours = N×4 appels avant fallback.
      - Avec 3 clés → jusqu'à 12 tentatives avant d'abandonner.

    Retourne le dict JSON parsé, ou None si tout a échoué → fallback local déclenché.
    """
    try:
        import requests as req
    except ImportError:
        logger.error("requests library not available")
        return None

    all_keys = _get_all_keys()
    if not all_keys:
        logger.error("Aucune GEMINI_API_KEY configurée dans Django settings")
        return None

    body = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT.strip()}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": _get_gemini_max_tokens(),
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    max_retries_per_key = _get_max_retries()
    MAX_POOL_ROUNDS = 2  # Nombre de tours sur l'ensemble du pool avant abandon

    for pool_round in range(MAX_POOL_ROUNDS):
        all_rate_limited = True  # Deviendra False si au moins une clé réussit ou échoue autrement

        for key_index, api_key in enumerate(all_keys):
            result = _try_single_key(req, body, api_key, max_retries_per_key)

            if result == "hard":
                # Erreur non-retryable : inutile d'essayer d'autres clés
                logger.error("Erreur hard sur clé %d/%d — abandon total", key_index + 1, len(all_keys))
                return None

            if result is not None:
                # Succès !
                if len(all_keys) > 1:
                    logger.info(
                        "Succès avec clé %d/%d (tour %d)",
                        key_index + 1, len(all_keys), pool_round + 1
                    )
                return result

            # result is None → cette clé a eu un 429 ou des 5xx épuisés
            # On continue vers la prochaine clé du pool
            if key_index < len(all_keys) - 1:
                logger.info(
                    "Clé %d/%d épuisée — passage à la clé suivante",
                    key_index + 1, len(all_keys)
                )

        # Toutes les clés ont eu un 429 sur ce tour
        if all_rate_limited and pool_round < MAX_POOL_ROUNDS - 1:
            delay = _compute_retry_delay(pool_round)
            logger.warning(
                "Toutes les clés (%d) sont rate-limitées (tour %d/%d). "
                "Pause de %.1fs avant de réessayer...",
                len(all_keys), pool_round + 1, MAX_POOL_ROUNDS, delay
            )
            time.sleep(delay)

    logger.error(
        "Pool de %d clé(s) épuisé après %d tour(s) — bascule vers fallback",
        len(all_keys), MAX_POOL_ROUNDS
    )
    return None


# ---------------------------------------------------------------------------
# Fallback — analyse locale sans LLM
# ---------------------------------------------------------------------------

def _local_fallback_analysis(texte_cdc: str, contexte_appel: dict) -> dict:
    """
    Analyse basique sans LLM : utilise revise_cdc_text() de cdc.py comme filet de sécurité.
    Retourne un rapport minimal si l'API est indisponible.
    """
    revision = revise_cdc_text(texte_cdc)
    alertes = []

    for i, term in enumerate(revision.get("alerts", []), start=1):
        alertes.append({
            "id": f"LOCAL_{i:03d}",
            "type": "terme_discriminant",
            "niveau": "attention",
            "extrait": term,
            "article_loi": "Art. 42 Loi 23-12",
            "message": f"Le terme '{term}' peut restreindre la concurrence.",
            "suggestion": f"Remplacer '{term}' par une formulation neutre.",
        })

    poids_technique = contexte_appel.get("poids_technique", 50)
    poids_financier = contexte_appel.get("poids_financier", 50)
    type_prestation = contexte_appel.get("type_prestation", "")

    if poids_technique + poids_financier != 100:
        alertes.append({
            "id": "LOCAL_POIDS_001",
            "type": "violation_loi",
            "niveau": "critique",
            "extrait": f"Pondération : {poids_technique}% technique / {poids_financier}% financier",
            "article_loi": "Art. 78 Loi 23-12",
            "message": "La somme des pondérations technique et financière doit être égale à 100%.",
            "suggestion": f"Ajuster les pondérations. Somme actuelle : {poids_technique + poids_financier}%.",
        })

    if type_prestation in ("travaux", "fournitures") and poids_financier < 30:
        alertes.append({
            "id": "LOCAL_POIDS_002",
            "type": "violation_loi",
            "niveau": "critique",
            "extrait": f"Pondération financière : {poids_financier}%",
            "article_loi": "Art. 78 Loi 23-12",
            "message": (
                f"Pour un marché de {type_prestation}, le critère financier doit représenter "
                "au moins 30% selon la Loi 23-12."
            ),
            "suggestion": f"Augmenter la pondération financière à au moins 30% (actuellement {poids_financier}%).",
        })

    score = max(0, 100 - len(alertes) * 15)

    return {
        "score_conformite": score,
        "resume_general": (
            "Analyse locale effectuée (service IA indisponible). "
            f"{len(alertes)} alerte(s) détectée(s) sur la base des règles de la Loi 23-12."
        ),
        "alertes_critiques": alertes,
        "analyse_sections": [],
        "suggestions_amelioration": [],
        "needs_human_validation": True,
        "_source": "local_fallback",
    }


# ---------------------------------------------------------------------------
# Point d'entrée principal — analyse CDC depuis texte
# ---------------------------------------------------------------------------

def analyse_cdc(texte_cdc: str, contexte_appel: dict) -> dict:
    """
    Analyse un CDC (texte extrait) en contexte avec les métadonnées de l'appel d'offres.

    Args:
        texte_cdc:       Texte brut extrait du CDC (via OCR ou extraction native).
        contexte_appel:  Dict contenant les champs du modèle AppelOffres pertinents.

    Returns:
        Dict structuré avec score_conformite, alertes_critiques, analyse_sections,
        suggestions_amelioration, needs_human_validation.
    """
    if not texte_cdc or len(texte_cdc.strip()) < MIN_CDC_TEXT_LENGTH:
        return {
            "score_conformite": 0,
            "resume_general": "Le texte du CDC est trop court ou illisible pour être analysé.",
            "alertes_critiques": [],
            "analyse_sections": [],
            "suggestions_amelioration": [],
            "needs_human_validation": True,
            "_source": "empty_text",
        }

    user_prompt = _build_user_prompt(texte_cdc, contexte_appel)
    result = _call_llm(user_prompt)

    if result is None:
        logger.warning("LLM unavailable, falling back to local analysis")
        return _local_fallback_analysis(texte_cdc, contexte_appel)

    # Garantir que needs_human_validation est True si score < 70 ou alertes critiques présentes
    critical_alerts = [
        a for a in result.get("alertes_critiques", [])
        if a.get("niveau") == "critique"
    ]
    if result.get("score_conformite", 100) < 70 or critical_alerts:
        result["needs_human_validation"] = True

    result["_source"] = "llm"
    return result


# ---------------------------------------------------------------------------
# Pipeline complet — depuis l'ID document
# ---------------------------------------------------------------------------

def run_aide_redaction_pipeline(id_document: int, contexte_appel: dict) -> dict:
    """
    Pipeline complet :
      1. Récupère le binaire du document CDC depuis le service documents
      2. Extrait le texte (OCR ou natif)
      3. Analyse le CDC avec le LLM

    Args:
        id_document:     ID du document CDC dans le service documents.
        contexte_appel:  Dict des champs AppelOffres.

    Returns:
        Dict avec les résultats d'analyse + métadonnées pipeline (ocr_engine, char_count, etc.)
    """
    # Étape 1 — Récupérer le binaire
    binary_result = fetch_document_binary(id_document)
    if not binary_result.get("ok"):
        logger.warning("Failed to fetch document binary for id=%s", id_document)
        return {
            "score_conformite": 0,
            "resume_general": "Impossible de récupérer le fichier CDC depuis le service documents.",
            "alertes_critiques": [],
            "analyse_sections": [],
            "suggestions_amelioration": [],
            "needs_human_validation": True,
            "_source": "fetch_error",
            "_error": binary_result.get("error", "unknown"),
        }

    content = binary_result.get("content", b"")
    content_type = binary_result.get("content_type", "")

    filename = _infer_filename(id_document, content_type)

    # Étape 2 — Extraire le texte
    ocr_result = extract_document_text(content, filename)
    texte_cdc = ocr_result.get("text", "")
    ocr_engine = ocr_result.get("engine", "none")

    logger.info(
        "CDC text extracted for document=%s: %d chars via engine=%s",
        id_document,
        len(texte_cdc),
        ocr_engine,
    )

    # Étape 3 — Analyser
    analyse = analyse_cdc(texte_cdc, contexte_appel)

    analyse["_pipeline"] = {
        "id_document": id_document,
        "ocr_engine": ocr_engine,
        "char_count": len(texte_cdc),
        "ocr_used": ocr_result.get("used", False),
    }

    return analyse


def _infer_filename(id_document: int, content_type: str) -> str:
    """Déduit un nom de fichier depuis le Content-Type pour guider l'OCR."""
    content_type = (content_type or "").lower()
    if "pdf" in content_type:
        return f"cdc_{id_document}.pdf"
    if "png" in content_type:
        return f"cdc_{id_document}.png"
    if "jpeg" in content_type or "jpg" in content_type:
        return f"cdc_{id_document}.jpg"
    if "tiff" in content_type:
        return f"cdc_{id_document}.tif"
    return f"cdc_{id_document}.pdf"