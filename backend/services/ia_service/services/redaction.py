"""
ia_service/services/redaction.py  — VERSION GROQ (100% GRATUIT)

Remplace Gemini par l'API Groq — compatible OpenAI, 100% gratuite.
Quotas Groq free tier : 14 400 req/jour, 6 000 tokens/min sur LLaMA 3.3 70B.

Configuration via settings.py (chargé depuis .env) :
    GROQ_API_KEY               — clé API Groq (obtenir sur console.groq.com)
    GROQ_MODEL                 — modèle à utiliser (défaut: llama-3.3-70b-versatile)
    GROQ_MAX_TOKENS            — tokens max en sortie (défaut: 2000)
    REMOTE_SERVICE_TIMEOUT_IA  — timeout HTTP en secondes (défaut: 60)
    GROQ_MAX_RETRIES           — nombre max de tentatives en cas d'erreur (défaut: 3)
    GROQ_RETRY_BASE_DELAY      — délai de base en secondes pour le backoff (défaut: 5)

Modèles Groq gratuits recommandés :
    llama-3.3-70b-versatile    → meilleure qualité (recommandé)
    llama-3.1-8b-instant       → plus rapide, quotas plus larges
    mixtral-8x7b-32768         → bon contexte long
"""

import json
import logging
import time
from typing import Optional

from django.conf import settings

from .cdc import revise_cdc_text
from .ocr import extract_document_text
from .integrations import fetch_document_binary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — lue depuis Django settings (settings.py → .env)
# ---------------------------------------------------------------------------

# Seuil en caractères en dessous duquel le CDC est considéré trop court
MIN_CDC_TEXT_LENGTH = 100

# Troncature du CDC pour rester dans les quotas Groq free tier
# LLaMA 3.3 70B : 6000 tokens/min — on limite à ~12 000 chars (≈ 3000 tokens)
MAX_CDC_CHARS = 12_000

# Codes HTTP qui déclenchent un retry
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


def _get_groq_api_key() -> str:
    return getattr(settings, "GROQ_API_KEY", "") or ""

def _get_groq_model() -> str:
    return getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")

def _get_groq_max_tokens() -> int:
    return int(getattr(settings, "GROQ_MAX_TOKENS", 2000))

def _get_timeout() -> float:
    return float(getattr(settings, "REMOTE_SERVICE_TIMEOUT_IA", 60.0))

def _get_max_retries() -> int:
    return int(getattr(settings, "GROQ_MAX_RETRIES", 3))

def _get_retry_base_delay() -> float:
    return float(getattr(settings, "GROQ_RETRY_BASE_DELAY", 5.0))


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
    Le CDC est tronqué à MAX_CDC_CHARS pour rester dans les quotas Groq free tier.
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

    # Tronquer le CDC si nécessaire pour rester dans les quotas
    texte_cdc_tronque = texte_cdc
    if len(texte_cdc) > MAX_CDC_CHARS:
        texte_cdc_tronque = texte_cdc[:MAX_CDC_CHARS] + "\n\n[... texte tronqué — analyse partielle ...]"
        logger.info(
            "CDC tronqué de %d à %d caractères pour respecter les quotas Groq",
            len(texte_cdc), MAX_CDC_CHARS
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

{texte_cdc_tronque}

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
# Parser de la réponse Groq (format OpenAI)
# ---------------------------------------------------------------------------

def _parse_groq_response(response_json: dict) -> Optional[dict]:
    """
    Extrait et parse le JSON retourné dans la réponse Groq (format OpenAI).
    Retourne le dict parsé, ou None si vide / invalide.
    """
    choices = response_json.get("choices", [])
    if not choices:
        logger.warning("Groq returned no choices")
        return None

    raw_text = choices[0].get("message", {}).get("content", "").strip()

    if not raw_text:
        logger.warning("Groq returned empty content")
        return None

    # Nettoyer les éventuels backticks markdown résiduels
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("JSON invalide dans la réponse Groq: %s\nRaw: %s", exc, raw_text[:500])
        return None


# ---------------------------------------------------------------------------
# Appel à l'API Groq avec retry + backoff
# ---------------------------------------------------------------------------

def _call_llm(user_prompt: str) -> Optional[dict]:
    """
    Appelle l'API Groq (compatible OpenAI) avec retry sur les erreurs transitoires.

    Stratégie :
      - Sur 429 (rate limit) : attend le délai Retry-After ou backoff exponentiel, puis retry.
      - Sur 5xx : backoff exponentiel, puis retry.
      - Sur 4xx autres (401, 400…) : abandon immédiat (erreur de config).

    Retourne le dict JSON parsé, ou None si tout a échoué → fallback local déclenché.
    """
    try:
        import requests as req
    except ImportError:
        logger.error("requests library not available")
        return None

    api_key = _get_groq_api_key()
    if not api_key:
        logger.error("Aucune GROQ_API_KEY configurée dans Django settings")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": _get_groq_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": _get_groq_max_tokens(),
        "temperature": 0.1,
        "response_format": {"type": "json_object"},  # Force JSON — pas de backticks
    }

    max_retries = _get_max_retries()
    base_delay = _get_retry_base_delay()

    for attempt in range(max_retries):
        try:
            logger.debug(
                "Groq API call — modèle %s, tentative %d/%d",
                _get_groq_model(), attempt + 1, max_retries
            )
            response = req.post(url, json=body, headers=headers, timeout=_get_timeout())

            # --- 429 : rate limit → attendre puis retry
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                logger.warning(
                    "Rate limit Groq (429) — pause %.1fs (tentative %d/%d)...",
                    wait, attempt + 1, max_retries
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
                logger.error("Rate limit Groq — retries épuisés après %d tentatives", max_retries)
                return None

            # --- Erreurs transitoires 5xx → backoff + retry
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < max_retries - 1:
                    wait = base_delay * (2 ** attempt)
                    logger.warning(
                        "Erreur transitoire Groq %d — retry dans %.1fs...",
                        response.status_code, wait
                    )
                    time.sleep(wait)
                    continue
                logger.error(
                    "Erreur transitoire Groq %d — retries épuisés", response.status_code
                )
                return None

            # --- Erreur non-retryable (400, 401, 403…) → abandon immédiat
            if not response.ok:
                logger.error(
                    "Groq API HTTP %d (non-retryable): %s",
                    response.status_code, response.text[:300]
                )
                return None

            # --- Succès : parser et retourner
            parsed = _parse_groq_response(response.json())
            if parsed is not None:
                logger.info(
                    "Groq API succès — modèle %s, tentative %d/%d",
                    _get_groq_model(), attempt + 1, max_retries
                )
            return parsed

        except req.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    "Timeout Groq — retry dans %.1fs (tentative %d/%d)...",
                    wait, attempt + 1, max_retries
                )
                time.sleep(wait)
            else:
                logger.error("Timeout Groq — retries épuisés après %d tentatives", max_retries)
                return None

        except req.exceptions.ConnectionError as exc:
            logger.error("Erreur réseau Groq API: %s", exc)
            return None

        except json.JSONDecodeError as exc:
            logger.warning("JSON invalide dans la réponse Groq: %s", exc)
            return None

        except Exception as exc:
            logger.error("Erreur inattendue Groq API: %s", exc)
            return None

    return None


# ---------------------------------------------------------------------------
# Fallback — analyse locale sans LLM
# ---------------------------------------------------------------------------

def _local_fallback_analysis(texte_cdc: str, contexte_appel: dict) -> dict:
    """
    Analyse basique sans LLM : utilise revise_cdc_text() de cdc.py comme filet de sécurité.
    Retourne un rapport minimal si l'API Groq est indisponible.
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
            "suggestion": (
                f"Augmenter la pondération financière à au moins 30% (actuellement {poids_financier}%)."
            ),
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
        logger.warning("LLM Groq indisponible, bascule vers l'analyse locale")
        return _local_fallback_analysis(texte_cdc, contexte_appel)

    # Garantir que needs_human_validation est True si score < 70 ou alertes critiques présentes
    critical_alerts = [
        a for a in result.get("alertes_critiques", [])
        if a.get("niveau") == "critique"
    ]
    if result.get("score_conformite", 100) < 70 or critical_alerts:
        result["needs_human_validation"] = True

    result["_source"] = "llm_groq"
    result["_model"] = _get_groq_model()
    return result


# ---------------------------------------------------------------------------
# Pipeline complet — depuis l'ID document
# ---------------------------------------------------------------------------

def run_aide_redaction_pipeline(id_document: int, contexte_appel: dict) -> dict:
    """
    Pipeline complet :
      1. Récupère le binaire du document CDC depuis le service documents
      2. Extrait le texte (OCR ou natif)
      3. Analyse le CDC avec Groq LLM

    Args:
        id_document:     ID du document CDC dans le service documents.
        contexte_appel:  Dict des champs AppelOffres.

    Returns:
        Dict avec les résultats d'analyse + métadonnées pipeline.
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
        id_document, len(texte_cdc), ocr_engine,
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