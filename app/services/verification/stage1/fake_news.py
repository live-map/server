"""
Fake news detection using BERT-based classifier.

Uses a pre-trained model to predict fake news probability.
"""

from dataclasses import dataclass

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

# Using a lightweight BERT fake news classifier
MODEL_NAME = "hamzab/roberta-fake-news-classification"

# Global pipeline instance
_classifier = None


@dataclass
class FakeNewsResult:
    """Result of fake news detection."""

    fake_probability: float  # 0.0-1.0 (0=real, 1=fake)
    real_probability: float
    label: str  # "FAKE" or "REAL"
    confidence: float


def load_model():
    """Load fake news classifier. Called during app lifespan startup."""
    global _classifier
    if _classifier is None:
        _classifier = pipeline(
            "text-classification",
            model=MODEL_NAME,
            tokenizer=MODEL_NAME,
            device="cpu",  # Use CPU for portability
            truncation=True,
            max_length=512,
        )
    return _classifier


def get_model():
    """Get the loaded classifier."""
    if _classifier is None:
        raise RuntimeError("Fake news classifier not loaded. Call load_model() first.")
    return _classifier


def detect_fake_news(text: str) -> FakeNewsResult:
    """
    Detect if text is fake news.

    Args:
        text: Input text to analyze

    Returns:
        FakeNewsResult with probability scores
    """
    classifier = get_model()

    # Truncate text if too long
    text = text[:2000] if len(text) > 2000 else text

    result = classifier(text)[0]

    label = result["label"]
    score = result["score"]

    # Model outputs "LABEL_0" (Real) or "LABEL_1" (Fake)
    # Or "FAKE"/"REAL" depending on the model
    if label in ("LABEL_1", "Fake", "FAKE"):
        fake_prob = score
        real_prob = 1 - score
        label_str = "FAKE"
    else:
        real_prob = score
        fake_prob = 1 - score
        label_str = "REAL"

    return FakeNewsResult(
        fake_probability=fake_prob,
        real_probability=real_prob,
        label=label_str,
        confidence=score,
    )
