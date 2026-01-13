"""
Stage 1 Pipeline: Local NLP verification.

V1 (Legacy - news articles):
- spaCy NER for location extraction (REQUIRED)
- Sentence Transformers for duplicate detection
- TextBlob for subjectivity analysis
- BERT for fake news detection

V2 (Social media optimized):
- spaCy NER for location extraction (OPTIONAL)
- Sentence Transformers for duplicate detection (dynamic threshold)
- Channel credibility scoring (NEW)
- Fake news/subjectivity DISABLED for short posts

Filter criteria V2:
- Duplicate → skip
- Score < 0.3 → skip
- Blocked channel → skip
"""

import asyncio
from dataclasses import dataclass

from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.services.verification.stage1 import duplicate, fake_news, spacy_ner, subjectivity
from app.services.verification.stage1.channel_credibility import (
    ChannelCredibilityResult,
    calculate_channel_credibility,
    calculate_text_length_threshold,
    get_default_credibility,
)


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


async def run_stage1_async(
    text: str,
    existing_embeddings: list[tuple[int, list[float]]] | None = None,
    min_score: float = 0.3,
) -> Stage1Result:
    """
    Run complete Stage 1 verification pipeline (async, parallel execution).

    All 4 ML models run in parallel using run_in_threadpool for CPU-bound tasks.
    This reduces Stage 1 time by ~50% compared to sequential execution.

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        min_score: Minimum score to continue to Stage 2

    Returns:
        Stage1Result with all analysis results
    """
    existing_embeddings = existing_embeddings or []

    # Run all 4 models in parallel (CPU-bound tasks in threadpool)
    ner_result, dup_result, subj_result, fake_result = await asyncio.gather(
        run_in_threadpool(spacy_ner.extract_locations, text),
        run_in_threadpool(duplicate.check_duplicate, text, existing_embeddings),
        run_in_threadpool(subjectivity.analyze_subjectivity, text),
        run_in_threadpool(fake_news.detect_fake_news, text),
    )

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
    if settings.STAGE1_ENABLE_FAKE_NEWS_MODEL:
        fake_news.load_model()


# =============================================================================
# V2: Social Media Optimized Pipeline
# =============================================================================


@dataclass
class Stage1ResultV2:
    """Stage 1 verification result for social media (v2)."""

    # Location (OPTIONAL in v2)
    locations: list[spacy_ner.LocationEntity]
    has_location: bool

    # Duplicate
    embedding: list[float]
    is_duplicate: bool
    max_similarity: float
    similar_feed_id: int | None
    duplicate_threshold: float  # Dynamic based on text length

    # Channel credibility (NEW in v2)
    channel_credibility: ChannelCredibilityResult
    channel_tier: int

    # Legacy scores (disabled for short posts)
    subjectivity_score: float | None
    fake_probability: float | None

    # Coordinates from Stage 0 (bonus in v2)
    has_coordinates: bool

    # Overall
    stage1_score: float
    should_continue: bool
    skip_reason: str | None
    score_breakdown: dict[str, float]


def calculate_stage1_score_v2(
    channel_score: float,
    has_location: bool,
    is_duplicate: bool,
    has_coordinates: bool = False,
) -> tuple[float, dict[str, float]]:
    """
    Calculate Stage 1 score for social media content (v2).

    V2 scoring:
    - Channel credibility: 0.4 weight (primary factor)
    - Non-duplicate: 0.4 base score
    - Location presence: 0.2 weight (optional bonus)
    - Coordinate extraction: 0.1 bonus

    Args:
        channel_score: Channel credibility score (0.0-1.0)
        has_location: Whether NER found a location
        is_duplicate: Whether content is duplicate
        has_coordinates: Whether Stage 0 extracted coordinates

    Returns:
        Tuple of (total_score, breakdown_dict)
    """
    breakdown: dict[str, float] = {}

    # Duplicate = immediate 0
    if is_duplicate:
        return 0.0, {"duplicate": 0.0}

    score = 0.0

    # Channel credibility (0-0.4)
    channel_contrib = channel_score * settings.STAGE1_CHANNEL_WEIGHT
    breakdown["channel"] = channel_contrib
    score += channel_contrib

    # Non-duplicate base score (0.4)
    base_score = 0.4
    breakdown["non_duplicate"] = base_score
    score += base_score

    # Location presence (0-0.2) - OPTIONAL
    if has_location:
        loc_bonus = settings.STAGE1_LOCATION_WEIGHT
        breakdown["location"] = loc_bonus
        score += loc_bonus
    else:
        breakdown["location"] = 0.0

    # Coordinate extraction bonus (0-0.1)
    if has_coordinates:
        coord_bonus = settings.STAGE1_COORDINATE_BONUS
        breakdown["coordinates"] = coord_bonus
        score += coord_bonus
    else:
        breakdown["coordinates"] = 0.0

    return min(score, 1.0), breakdown


async def run_stage1_v2_async(
    text: str,
    existing_embeddings: list[tuple[int, list[float]]] | None = None,
    channel_info: dict | None = None,
    stage0_result=None,
    min_score: float = 0.3,
) -> Stage1ResultV2:
    """
    Run Stage 1 verification pipeline v2 (social media optimized).

    Changes from v1:
    - Location is OPTIONAL (not a skip condition)
    - Channel credibility is primary scoring factor
    - Fake news/subjectivity disabled for short posts
    - Dynamic duplicate threshold based on text length

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        channel_info: Channel metadata (subscriber_count, channel_age_days, etc.)
        stage0_result: Result from Stage 0 preprocessing
        min_score: Minimum score to continue to Stage 2

    Returns:
        Stage1ResultV2 with all analysis results
    """
    existing_embeddings = existing_embeddings or []
    channel_info = channel_info or {}

    # Determine text length for dynamic threshold
    text_length = len(text)
    if stage0_result and hasattr(stage0_result, "text_length"):
        text_length = stage0_result.text_length

    dup_threshold = calculate_text_length_threshold(text_length)

    # Determine if we should run legacy models
    is_short_post = text_length < 280
    run_legacy = not is_short_post and (
        settings.STAGE1_ENABLE_FAKE_NEWS_MODEL or settings.STAGE1_ENABLE_SUBJECTIVITY
    )

    # Run NER and duplicate check in parallel
    tasks = [
        run_in_threadpool(spacy_ner.extract_locations, text),
        run_in_threadpool(duplicate.check_duplicate, text, existing_embeddings, dup_threshold),
    ]

    # Optionally run legacy models
    if run_legacy and settings.STAGE1_ENABLE_SUBJECTIVITY:
        tasks.append(run_in_threadpool(subjectivity.analyze_subjectivity, text))
    if run_legacy and settings.STAGE1_ENABLE_FAKE_NEWS_MODEL:
        tasks.append(run_in_threadpool(fake_news.detect_fake_news, text))

    results = await asyncio.gather(*tasks)

    # Unpack results
    ner_result = results[0]
    dup_result = results[1]
    subj_result = results[2] if run_legacy and settings.STAGE1_ENABLE_SUBJECTIVITY else None
    fake_result = results[-1] if run_legacy and settings.STAGE1_ENABLE_FAKE_NEWS_MODEL else None

    # Calculate channel credibility
    channel_cred = calculate_channel_credibility(
        subscriber_count=channel_info.get("subscriber_count"),
        channel_age_days=channel_info.get("channel_age_days"),
        is_verified=channel_info.get("is_verified", False),
        historical_accuracy=channel_info.get("historical_accuracy"),
        is_trusted=channel_info.get("is_trusted"),
        is_blocked=channel_info.get("is_blocked", False),
    )

    # Check for coordinates from Stage 0
    has_coordinates = False
    if stage0_result and hasattr(stage0_result, "has_coordinates"):
        has_coordinates = stage0_result.has_coordinates

    # Calculate score (v2)
    stage1_score, breakdown = calculate_stage1_score_v2(
        channel_score=channel_cred.score,
        has_location=ner_result.has_location,
        is_duplicate=dup_result.is_duplicate,
        has_coordinates=has_coordinates,
    )

    # Determine skip conditions (v2 - location is NOT a skip condition)
    skip_reason = None
    should_continue = True

    if channel_cred.is_blocked:
        should_continue = False
        skip_reason = "Channel is blocked"
    elif dup_result.is_duplicate:
        should_continue = False
        skip_reason = f"Duplicate of feed {dup_result.similar_feed_id}"
    elif stage1_score < min_score:
        should_continue = False
        skip_reason = f"Score too low: {stage1_score:.3f} < {min_score}"

    return Stage1ResultV2(
        # Location
        locations=ner_result.locations,
        has_location=ner_result.has_location,
        # Duplicate
        embedding=dup_result.embedding,
        is_duplicate=dup_result.is_duplicate,
        max_similarity=dup_result.max_similarity,
        similar_feed_id=dup_result.similar_feed_id,
        duplicate_threshold=dup_threshold,
        # Channel credibility
        channel_credibility=channel_cred,
        channel_tier=channel_cred.tier,
        # Legacy scores
        subjectivity_score=subj_result.subjectivity if subj_result else None,
        fake_probability=fake_result.fake_probability if fake_result else None,
        # Coordinates
        has_coordinates=has_coordinates,
        # Overall
        stage1_score=round(stage1_score, 3),
        should_continue=should_continue,
        skip_reason=skip_reason,
        score_breakdown=breakdown,
    )
