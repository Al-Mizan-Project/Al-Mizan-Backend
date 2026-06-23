"""
Semantic embedding service for multilingual document type recognition.

Uses ``sentence-transformers/paraphrase-multilingual-mpnet-base-v2`` to compute
cosine similarity between incoming text and a pre-built reference corpus of
canonical document type labels (French + Arabic).

The model is lazy-loaded once (singleton) and reference embeddings are cached
in memory for fast inference (~5-15 ms per query on CPU).
"""

import logging
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference corpus — canonical labels for the 4 supported document types
# Each canonical type maps to a list of representative labels (FR + AR).
# These are embedded once at startup and cached.
# ---------------------------------------------------------------------------
REFERENCE_LABELS: Dict[str, List[str]] = {
    "offre_technique": [
        # French
        "offre technique",
        "mémoire technique",
        "dossier technique",
        "fiche technique",
        "proposition technique",
        "spécifications techniques",
        # Arabic (MSA)
        "العرض التقني",
        "المذكرة التقنية",
        "الملف التقني",
        "المواصفات التقنية",
        "الاقتراح التقني",
    ],
    "offre_financiere": [
        # French
        "offre financière",
        "bordereau des prix",
        "bordereau prix unitaires",
        "devis quantitatif",
        "devis estimatif",
        "soumission financière",
        "proposition financière",
        "montant de l'offre",
        # Arabic (MSA)
        "العرض المالي",
        "كشف الأسعار",
        "جدول الأسعار",
        "التقدير المالي",
        "العرض المالي للمناقصة",
    ],
    "declaration_souscrire": [
        # French
        "déclaration à souscrire",
        "déclaration de souscription",
        "lettre de soumission",
        "engagement du soumissionnaire",
        # Arabic (MSA)
        "التصريح بالاكتتاب",
        "رسالة التعهد",
        "التزام المتعهد",
        "تصريح الاكتتاب",
    ],
    "declaration_probite": [
        # French
        "déclaration de probité",
        "engagement de probité",
        "attestation de probité",
        # Arabic (MSA)
        "تصريح النزاهة",
        "إقرار بالنزاهة",
        "شهادة النزاهة",
        "التزام بالنزاهة",
    ],
}


# ---------------------------------------------------------------------------
# Singleton model holder — thread-safe lazy loading
# ---------------------------------------------------------------------------
class _EmbeddingModelHolder:
    """Thread-safe singleton that lazily loads the sentence-transformers model."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._reference_embeddings: Optional[np.ndarray] = None
        self._reference_labels_flat: List[Tuple[str, str]] = []  # (canonical, label)

    def _get_model_name(self) -> str:
        return getattr(
            settings,
            "EMBEDDING_MODEL_NAME",
            "paraphrase-multilingual-mpnet-base-v2",
        )

    def _load_model(self):
        """Load model on first use. Called inside the lock."""
        if self._model is not None:
            return

        model_name = self._get_model_name()
        logger.info("Loading embedding model: %s …", model_name)

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
        except Exception as exc:
            logger.error("Failed to load embedding model '%s': %s", model_name, exc)
            raise

        # Pre-compute reference embeddings
        self._reference_labels_flat = []
        all_labels: List[str] = []
        for canonical, labels in REFERENCE_LABELS.items():
            for label in labels:
                self._reference_labels_flat.append((canonical, label))
                all_labels.append(label)

        self._reference_embeddings = self._model.encode(
            all_labels, normalize_embeddings=True, show_progress_bar=False
        )
        logger.info(
            "Embedding model loaded. %d reference labels pre-computed.",
            len(all_labels),
        )

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                self._load_model()
        return self._model

    @property
    def reference_embeddings(self) -> np.ndarray:
        if self._reference_embeddings is None:
            with self._lock:
                self._load_model()
        return self._reference_embeddings

    @property
    def reference_labels_flat(self) -> List[Tuple[str, str]]:
        if not self._reference_labels_flat:
            with self._lock:
                self._load_model()
        return self._reference_labels_flat


_holder = _EmbeddingModelHolder()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _get_threshold() -> float:
    return float(
        getattr(settings, "EMBEDDING_SIMILARITY_THRESHOLD", 0.55)
    )


def semantic_match_document_type(
    text: str,
    threshold: Optional[float] = None,
) -> str:
    """
    Match *text* against the reference corpus using cosine similarity.

    Returns the canonical document type (e.g. ``"offre_technique"``) when the
    best similarity score is **>=** *threshold*, otherwise returns ``""``.

    Parameters
    ----------
    text : str
        The text to match (filename, title, short OCR snippet — NOT full
        document text).
    threshold : float, optional
        Minimum cosine similarity to accept a match.  Falls back to
        ``settings.EMBEDDING_SIMILARITY_THRESHOLD`` (default ``0.55``).
    """
    if not text or not text.strip():
        return ""

    if threshold is None:
        threshold = _get_threshold()

    try:
        query_embedding = _holder.model.encode(
            [text.strip()], normalize_embeddings=True, show_progress_bar=False
        )
    except Exception as exc:
        logger.warning("Embedding encode failed for text=%r: %s", text[:80], exc)
        return ""

    # Cosine similarity (embeddings are already L2-normalised → dot product)
    similarities = np.dot(_holder.reference_embeddings, query_embedding.T).flatten()

    best_idx = int(np.argmax(similarities))
    best_score = float(similarities[best_idx])
    best_canonical, best_label = _holder.reference_labels_flat[best_idx]

    logger.debug(
        "Semantic match: text=%r → best=%s (label=%r, score=%.4f, threshold=%.2f)",
        text[:60],
        best_canonical,
        best_label,
        best_score,
        threshold,
    )

    if best_score >= threshold:
        return best_canonical

    return ""
