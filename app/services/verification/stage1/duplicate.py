"""
Duplicate detection using Sentence Transformers.

Uses all-MiniLM-L6-v2 for 384-dimensional embeddings.
Compares new content against existing embeddings via cosine similarity.
"""

from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer

# Model produces 384-dimensional embeddings (matches Feed.embedding column)
MODEL_NAME = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.85  # Above this = duplicate

# Global model instance
_model: SentenceTransformer | None = None


@dataclass
class DuplicateResult:
    """Result of duplicate detection."""

    embedding: list[float]
    is_duplicate: bool
    max_similarity: float
    similar_feed_id: int | None


def load_model() -> SentenceTransformer:
    """Load Sentence Transformer model. Called during app lifespan startup."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_model() -> SentenceTransformer:
    """Get the loaded model."""
    if _model is None:
        raise RuntimeError("Sentence Transformer model not loaded. Call load_model() first.")
    return _model


def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding for text.

    Args:
        text: Input text

    Returns:
        384-dimensional embedding vector
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def check_duplicate(
    text: str, existing_embeddings: list[tuple[int, list[float]]], threshold: float = SIMILARITY_THRESHOLD
) -> DuplicateResult:
    """
    Check if text is duplicate of existing content.

    Args:
        text: New text to check
        existing_embeddings: List of (feed_id, embedding) tuples from database
        threshold: Similarity threshold for duplicate detection

    Returns:
        DuplicateResult with embedding and duplicate status
    """
    embedding = generate_embedding(text)

    max_similarity = 0.0
    similar_feed_id = None

    for feed_id, existing_emb in existing_embeddings:
        similarity = cosine_similarity(embedding, existing_emb)
        if similarity > max_similarity:
            max_similarity = similarity
            similar_feed_id = feed_id

    return DuplicateResult(
        embedding=embedding,
        is_duplicate=max_similarity >= threshold,
        max_similarity=max_similarity,
        similar_feed_id=similar_feed_id if max_similarity >= threshold else None,
    )
