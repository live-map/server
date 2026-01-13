"""
Channel credibility scoring stub.

This module has been deprecated. Channel credibility is now handled
by the autonomous agent system.

The functions below return default values for backward compatibility.
"""

from dataclasses import dataclass


@dataclass
class ChannelCredibilityResult:
    """Channel credibility result (stub)."""

    channel_score: float = 0.7
    is_blocked: bool = False
    tier: int = 3


def calculate_channel_credibility(
    channel_id: str | None = None,
    platform: str = "TELEGRAM",
) -> ChannelCredibilityResult:
    """Return default credibility (stub)."""
    return ChannelCredibilityResult()


def calculate_text_length_threshold(text: str) -> int:
    """Return minimum text length threshold (stub)."""
    return 20


def get_default_credibility() -> ChannelCredibilityResult:
    """Return default credibility (stub)."""
    return ChannelCredibilityResult()
