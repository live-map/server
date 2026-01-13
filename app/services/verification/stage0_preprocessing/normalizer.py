"""
Text normalizer for social media content.

Handles:
- Hashtag normalization (#Ukraine -> Ukraine)
- Mention removal (@username)
- Emoji handling
- URL extraction and normalization
- Whitespace cleanup
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class NormalizationResult:
    """Result of text normalization."""

    original_text: str
    normalized_text: str
    extracted_hashtags: list[str]
    extracted_mentions: list[str]
    extracted_urls: list[str]
    has_emojis: bool
    text_length_original: int
    text_length_normalized: int


# Regex patterns
HASHTAG_PATTERN = re.compile(r"#(\w+)", re.UNICODE)
MENTION_PATTERN = re.compile(r"@(\w+)", re.UNICODE)
URL_PATTERN = re.compile(
    r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\-.?&=%#]*",
    re.UNICODE,
)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)
MULTIPLE_SPACES_PATTERN = re.compile(r"\s+")
NEWLINE_PATTERN = re.compile(r"\n{3,}")


def normalize_text(text: str, keep_hashtags: bool = True, keep_emojis: bool = False) -> NormalizationResult:
    """
    Normalize social media text for verification.

    Args:
        text: Raw text from social media
        keep_hashtags: If True, convert #tag to tag. If False, remove entirely.
        keep_emojis: If True, keep emojis. If False, remove them.

    Returns:
        NormalizationResult with normalized text and extracted elements
    """
    original_text = text
    original_length = len(text)

    # Extract elements before removal
    hashtags = HASHTAG_PATTERN.findall(text)
    mentions = MENTION_PATTERN.findall(text)
    urls = URL_PATTERN.findall(text)
    has_emojis = bool(EMOJI_PATTERN.search(text))

    # Normalize text
    normalized = text

    # Handle hashtags
    if keep_hashtags:
        # Convert #Ukraine to Ukraine
        normalized = HASHTAG_PATTERN.sub(r"\1", normalized)
    else:
        # Remove hashtags entirely
        normalized = HASHTAG_PATTERN.sub("", normalized)

    # Remove mentions
    normalized = MENTION_PATTERN.sub("", normalized)

    # Remove URLs (we track them separately)
    normalized = URL_PATTERN.sub("[URL]", normalized)

    # Handle emojis
    if not keep_emojis:
        normalized = EMOJI_PATTERN.sub("", normalized)

    # Clean up whitespace
    normalized = MULTIPLE_SPACES_PATTERN.sub(" ", normalized)
    normalized = NEWLINE_PATTERN.sub("\n\n", normalized)
    normalized = normalized.strip()

    # Normalize unicode
    normalized = unicodedata.normalize("NFKC", normalized)

    return NormalizationResult(
        original_text=original_text,
        normalized_text=normalized,
        extracted_hashtags=hashtags,
        extracted_mentions=mentions,
        extracted_urls=urls,
        has_emojis=has_emojis,
        text_length_original=original_length,
        text_length_normalized=len(normalized),
    )


def is_mostly_hashtags(text: str, threshold: float = 0.5) -> bool:
    """
    Check if text is mostly hashtags (likely spam or tag aggregation).

    Args:
        text: Text to check
        threshold: Ratio of hashtag characters to total

    Returns:
        True if text is mostly hashtags
    """
    hashtag_chars = sum(len(tag) + 1 for tag in HASHTAG_PATTERN.findall(text))  # +1 for #
    total_chars = len(text.strip())

    if total_chars == 0:
        return True

    return hashtag_chars / total_chars >= threshold


def extract_quoted_text(text: str) -> list[str]:
    """
    Extract quoted text (potential original source content).

    Args:
        text: Text to search

    Returns:
        List of quoted strings
    """
    # Various quote patterns
    patterns = [
        re.compile(r'"([^"]+)"'),  # Double quotes
        re.compile(r"'([^']+)'"),  # Single quotes
        re.compile(r"「([^」]+)」"),  # Japanese quotes
        re.compile(r"«([^»]+)»"),  # Guillemets
    ]

    quotes = []
    for pattern in patterns:
        quotes.extend(pattern.findall(text))

    return quotes
