"""
Stage 1 Pipeline: Local NLP verification.

Combines all Stage 1 checks:
- spaCy NER for location extraction
- Sentence Transformers for duplicate detection
- TextBlob for subjectivity analysis
- BERT for fake news detection

Filter criteria:
- No location → skip (can't map it)
- Duplicate (similarity > 0.85) → skip
- Stage 1 score < 0.3 → skip
"""

from dataclasses import dataclass

from app.services.verification.stage1 import duplicate, fake_news, spacy_ner, subjectivity


@dataclass
class Stage1Result:
    """Complete Stage 1 verification result."""

    # Location
    locations: list[spacy_ner.LocationEntity]
    has_location: bool

    # Duplicate
    embedding: list[float]
    is_duplicate: bool
    max_similarity: float
    similar_feed_id: int | None

    # Subjectivity
    subjectivity_score: float
    polarity: float
    is_objective: bool

    # Fake news
    fake_probability: float
    fake_label: str

    # Overall
    stage1_score: float
    should_continue: bool
    skip_reason: str | None


def calculate_stage1_score(
    has_location: bool,
    is_duplicate: bool,
    subjectivity_score: float,
    fake_probability: float,
) -> float:
    """
    Calculate overall Stage 1 credibility score.

    Higher score = more credible
    - Has location: +0.25
    - Not duplicate: +0.25
    - Objectivity: (1 - subjectivity) * 0.25
    - Not fake: (1 - fake_prob) * 0.25
    """
    score = 0.0

    if has_location:
        score += 0.25

    if not is_duplicate:
        score += 0.25

    # Objectivity contribution (0-0.25)
    score += (1 - subjectivity_score) * 0.25

    # Credibility contribution (0-0.25)
    score += (1 - fake_probability) * 0.25

    return round(score, 3)


def run_stage1(
    text: str,
    existing_embeddings: list[tuple[int, list[float]]] | None = None,
    min_score: float = 0.3,
) -> Stage1Result:
    """
    Run complete Stage 1 verification pipeline.

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        min_score: Minimum score to continue to Stage 2

    Returns:
        Stage1Result with all analysis results
    """
    existing_embeddings = existing_embeddings or []

    # 1. Extract locations
    ner_result = spacy_ner.extract_locations(text)

    # 2. Check duplicates
    dup_result = duplicate.check_duplicate(text, existing_embeddings)

    # 3. Analyze subjectivity
    subj_result = subjectivity.analyze_subjectivity(text)

    # 4. Detect fake news
    fake_result = fake_news.detect_fake_news(text)

    # Calculate overall score
    stage1_score = calculate_stage1_score(
        has_location=ner_result.has_location,
        is_duplicate=dup_result.is_duplicate,
        subjectivity_score=subj_result.subjectivity,
        fake_probability=fake_result.fake_probability,
    )

    # Determine if should continue to Stage 2
    skip_reason = None
    should_continue = True

    if not ner_result.has_location:
        should_continue = False
        skip_reason = "No location found"
    elif dup_result.is_duplicate:
        should_continue = False
        skip_reason = f"Duplicate of feed {dup_result.similar_feed_id}"
    elif stage1_score < min_score:
        should_continue = False
        skip_reason = f"Score too low: {stage1_score} < {min_score}"

    return Stage1Result(
        # Location
        locations=ner_result.locations,
        has_location=ner_result.has_location,
        # Duplicate
        embedding=dup_result.embedding,
        is_duplicate=dup_result.is_duplicate,
        max_similarity=dup_result.max_similarity,
        similar_feed_id=dup_result.similar_feed_id,
        # Subjectivity
        subjectivity_score=subj_result.subjectivity,
        polarity=subj_result.polarity,
        is_objective=subj_result.is_objective,
        # Fake news
        fake_probability=fake_result.fake_probability,
        fake_label=fake_result.label,
        # Overall
        stage1_score=stage1_score,
        should_continue=should_continue,
        skip_reason=skip_reason,
    )


def load_all_models():
    """Load all Stage 1 models. Call during app startup."""
    spacy_ner.load_model()
    duplicate.load_model()
    fake_news.load_model()
