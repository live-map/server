"""
Channel credibility calculation for social media sources.

Calculates credibility scores based on:
- Subscriber count
- Channel age
- Verification status
- Historical accuracy
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings


@dataclass
class ChannelCredibilityResult:
    """Result of channel credibility calculation."""

    score: float  # 0.0-1.0
    tier: int  # 1 (best) - 5 (unknown)
    breakdown: dict[str, float]  # Component scores
    is_trusted: bool | None  # Manual override if set
    is_blocked: bool


def calculate_channel_credibility(
    subscriber_count: int | None = None,
    channel_age_days: int | None = None,
    is_verified: bool = False,
    historical_accuracy: float | None = None,
    is_trusted: bool | None = None,
    is_blocked: bool = False,
) -> ChannelCredibilityResult:
    """
    Calculate channel credibility score.

    Args:
        subscriber_count: Number of subscribers
        channel_age_days: Days since channel creation
        is_verified: Platform verification status
        historical_accuracy: Past verification accuracy (0.0-1.0)
        is_trusted: Manual trust override
        is_blocked: Channel is blocked

    Returns:
        ChannelCredibilityResult with score and tier
    """
    # If blocked, return minimum score
    if is_blocked:
        return ChannelCredibilityResult(
            score=0.0,
            tier=5,
            breakdown={"blocked": 0.0},
            is_trusted=is_trusted,
            is_blocked=True,
        )

    # If manually trusted, return high score
    if is_trusted is True:
        return ChannelCredibilityResult(
            score=0.85,
            tier=2,
            breakdown={"manual_trust": 0.85},
            is_trusted=True,
            is_blocked=False,
        )

    breakdown: dict[str, float] = {}
    score = 0.0

    # Subscriber count (0-0.25)
    subscriber_score = 0.0
    if subscriber_count is not None:
        if subscriber_count >= settings.CHANNEL_SUBSCRIBER_TIER1:
            subscriber_score = 0.25
        elif subscriber_count >= settings.CHANNEL_SUBSCRIBER_TIER2:
            subscriber_score = 0.20
        elif subscriber_count >= settings.CHANNEL_SUBSCRIBER_TIER3:
            subscriber_score = 0.10
        else:
            subscriber_score = 0.05
    breakdown["subscribers"] = subscriber_score
    score += subscriber_score

    # Channel age (0-0.25)
    age_score = 0.0
    if channel_age_days is not None:
        if channel_age_days >= settings.CHANNEL_AGE_TIER1_DAYS:
            age_score = 0.25
        elif channel_age_days >= settings.CHANNEL_AGE_TIER2_DAYS:
            age_score = 0.15
        elif channel_age_days >= 180:
            age_score = 0.10
        else:
            age_score = 0.05
    breakdown["age"] = age_score
    score += age_score

    # Verified status (0-0.2)
    verified_score = 0.20 if is_verified else 0.0
    breakdown["verified"] = verified_score
    score += verified_score

    # Historical accuracy (0-0.3)
    accuracy_score = 0.0
    if historical_accuracy is not None:
        accuracy_score = historical_accuracy * 0.3
    else:
        # Unknown accuracy - neutral score
        accuracy_score = 0.15
    breakdown["accuracy"] = accuracy_score
    score += accuracy_score

    # Calculate tier
    if score >= 0.8:
        tier = 1
    elif score >= 0.6:
        tier = 2
    elif score >= 0.4:
        tier = 3
    elif score >= 0.2:
        tier = 4
    else:
        tier = 5

    return ChannelCredibilityResult(
        score=min(score, 1.0),
        tier=tier,
        breakdown=breakdown,
        is_trusted=is_trusted,
        is_blocked=False,
    )


def calculate_channel_credibility_from_model(channel) -> ChannelCredibilityResult:
    """
    Calculate credibility from a Channel model instance.

    Args:
        channel: Channel model instance

    Returns:
        ChannelCredibilityResult
    """
    return calculate_channel_credibility(
        subscriber_count=channel.subscriber_count,
        channel_age_days=channel.channel_age_days,
        is_verified=channel.is_verified,
        historical_accuracy=channel.historical_accuracy,
        is_trusted=channel.is_trusted,
        is_blocked=channel.is_blocked,
    )


def get_default_credibility() -> ChannelCredibilityResult:
    """
    Get default credibility for unknown channels.

    Returns:
        ChannelCredibilityResult with neutral score
    """
    return ChannelCredibilityResult(
        score=0.35,  # Neutral-low score
        tier=settings.CHANNEL_DEFAULT_TIER,
        breakdown={"unknown": 0.35},
        is_trusted=None,
        is_blocked=False,
    )


def calculate_text_length_threshold(text_length: int) -> float:
    """
    Get duplicate detection threshold based on text length.

    Shorter texts need higher similarity to be duplicates
    (to avoid false positives).

    Args:
        text_length: Length of normalized text

    Returns:
        Similarity threshold (0.0-1.0)
    """
    if text_length < 100:
        return settings.DUPLICATE_THRESHOLD_SHORT
    elif text_length < 280:
        return settings.DUPLICATE_THRESHOLD_MEDIUM
    else:
        return settings.DUPLICATE_THRESHOLD_LONG
