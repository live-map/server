"""
Subjectivity analysis using TextBlob.

Measures how subjective vs objective the text is.
- 0.0 = very objective (factual)
- 1.0 = very subjective (opinion-based)
"""

from dataclasses import dataclass

from textblob import TextBlob


@dataclass
class SubjectivityResult:
    """Result of subjectivity analysis."""

    subjectivity: float  # 0.0-1.0 (0=objective, 1=subjective)
    polarity: float  # -1.0 to 1.0 (negative to positive sentiment)
    is_objective: bool  # True if subjectivity < threshold


# Threshold for considering text objective
OBJECTIVITY_THRESHOLD = 0.4


def analyze_subjectivity(text: str, threshold: float = OBJECTIVITY_THRESHOLD) -> SubjectivityResult:
    """
    Analyze subjectivity of text.

    Args:
        text: Input text to analyze
        threshold: Subjectivity threshold for objective classification

    Returns:
        SubjectivityResult with scores
    """
    blob = TextBlob(text)

    # TextBlob sentiment returns (polarity, subjectivity)
    polarity = blob.sentiment.polarity
    subjectivity = blob.sentiment.subjectivity

    return SubjectivityResult(
        subjectivity=subjectivity,
        polarity=polarity,
        is_objective=subjectivity < threshold,
    )
