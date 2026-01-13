"""
Repost/forward detector for social media content.

Detects:
- Telegram forwards (Forwarded from:)
- X/Twitter retweets (RT @)
- Quote tweets
- Cross-platform reposts
"""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class RepostDetectionResult:
    """Result of repost detection."""

    is_repost: bool
    repost_type: Literal["FORWARD", "RETWEET", "QUOTE", "CROSSPOST", "ORIGINAL"] | None
    original_source: str | None  # Channel/account name
    original_source_id: str | None  # Platform-specific ID if available
    confidence: float  # 0.0-1.0
    extracted_original_text: str | None  # Original content if quote


# Telegram forward patterns
TELEGRAM_FORWARD_PATTERNS = [
    re.compile(r"^Forwarded from[:\s]+(.+?)(?:\n|$)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^↩️?\s*Forwarded from[:\s]+(.+?)(?:\n|$)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\[Forwarded from (.+?)\]", re.IGNORECASE | re.MULTILINE),
]

# X/Twitter retweet patterns
RETWEET_PATTERNS = [
    re.compile(r"^RT\s+@(\w+)[:\s]", re.IGNORECASE),
    re.compile(r"^🔁\s*RT\s+@(\w+)", re.IGNORECASE),
]

# Quote tweet patterns (reference to another tweet)
QUOTE_PATTERNS = [
    re.compile(r"https://(?:twitter\.com|x\.com)/(\w+)/status/(\d+)"),
]

# Cross-platform patterns
CROSSPOST_PATTERNS = [
    re.compile(r"(?:via|from|source)[:\s]+@?(\w+)(?:\s+on\s+(telegram|twitter|x))?", re.IGNORECASE),
    re.compile(r"Originally posted (?:by|on)[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
]

# Common repost indicators
REPOST_INDICATORS = [
    "forwarded from",
    "rt @",
    "retweet",
    "via @",
    "originally posted",
    "source:",
    "from:",
    "🔁",
    "↩️",
]


def detect_repost(text: str, platform: str | None = None) -> RepostDetectionResult:
    """
    Detect if content is a repost/forward.

    Args:
        text: Text content to analyze
        platform: Source platform (TELEGRAM, X) if known

    Returns:
        RepostDetectionResult with detection details
    """
    text_lower = text.lower()

    # Quick check for repost indicators
    has_indicator = any(ind in text_lower for ind in REPOST_INDICATORS)

    if not has_indicator:
        return RepostDetectionResult(
            is_repost=False,
            repost_type="ORIGINAL",
            original_source=None,
            original_source_id=None,
            confidence=0.90,
            extracted_original_text=None,
        )

    # Check Telegram forwards
    if platform == "TELEGRAM" or platform is None:
        for pattern in TELEGRAM_FORWARD_PATTERNS:
            match = pattern.search(text)
            if match:
                source = match.group(1).strip()
                # Extract original text (everything after the forward header)
                original_text = text[match.end() :].strip()
                return RepostDetectionResult(
                    is_repost=True,
                    repost_type="FORWARD",
                    original_source=source,
                    original_source_id=None,
                    confidence=0.95,
                    extracted_original_text=original_text if original_text else None,
                )

    # Check X/Twitter retweets
    if platform == "X" or platform is None:
        for pattern in RETWEET_PATTERNS:
            match = pattern.search(text)
            if match:
                return RepostDetectionResult(
                    is_repost=True,
                    repost_type="RETWEET",
                    original_source=f"@{match.group(1)}",
                    original_source_id=None,
                    confidence=0.95,
                    extracted_original_text=None,
                )

        # Check quote tweets
        for pattern in QUOTE_PATTERNS:
            match = pattern.search(text)
            if match:
                return RepostDetectionResult(
                    is_repost=True,
                    repost_type="QUOTE",
                    original_source=f"@{match.group(1)}",
                    original_source_id=match.group(2),
                    confidence=0.90,
                    extracted_original_text=None,
                )

    # Check cross-platform patterns
    for pattern in CROSSPOST_PATTERNS:
        match = pattern.search(text)
        if match:
            source = match.group(1).strip()
            return RepostDetectionResult(
                is_repost=True,
                repost_type="CROSSPOST",
                original_source=source,
                original_source_id=None,
                confidence=0.70,
                extracted_original_text=None,
            )

    # Has indicator but couldn't parse - low confidence repost
    return RepostDetectionResult(
        is_repost=True,
        repost_type="FORWARD",
        original_source=None,
        original_source_id=None,
        confidence=0.50,
        extracted_original_text=None,
    )


def extract_original_author(text: str) -> str | None:
    """
    Try to extract original author from text.

    Args:
        text: Text to analyze

    Returns:
        Original author name if found
    """
    result = detect_repost(text)
    return result.original_source
