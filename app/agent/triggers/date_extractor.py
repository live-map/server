"""
URL Date Extractor - Extract publication dates from news article URLs and content

Many news websites include publication dates in their URLs:
- /2026/01/23/article-title
- /2026-01-23/article
- /news/20260123-article
- Unix timestamps: /news/article-1769158862.html

This module extracts these dates and compares with API-provided dates
to detect stale/old articles being re-indexed.

Enhanced Features (v2):
- Content-based date extraction from title/text
- Past year detection to catch old events
- 4-Layer validation for trigger events
"""

import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Any

logger = logging.getLogger(__name__)

# Current year for past year detection
CURRENT_YEAR = datetime.utcnow().year

# URL date patterns (ordered by reliability)
URL_DATE_PATTERNS = [
    # /2026/01/23/ or /2026/1/23/
    (r"/(\d{4})/(\d{1,2})/(\d{1,2})/", "ymd_slash"),
    # /2026-01-23/ or /2026-1-23/
    (r"/(\d{4})-(\d{1,2})-(\d{1,2})", "ymd_dash"),
    # /20260123/ or -20260123- or _20260123_
    (r"[/_-](\d{4})(\d{2})(\d{2})[/_-]", "ymd_compact"),
    # /23-01-2026/ (day-month-year)
    (r"/(\d{1,2})-(\d{1,2})-(\d{4})/", "dmy_dash"),
    # /01-23-2026/ (month-day-year, US format)
    (r"/(\d{1,2})-(\d{1,2})-(\d{4})/", "mdy_dash"),
    # /2026/01/ (year/month only - less precise)
    (r"/(\d{4})/(\d{1,2})(?:/|$)", "ym_only"),
]

# Unix timestamp pattern (10-digit or 13-digit)
UNIX_TIMESTAMP_PATTERN = re.compile(r"[/_-](\d{10,13})[/_.-]|[/_-](\d{10,13})$")


def extract_date_from_url(url: str) -> datetime | None:
    """
    Extract publication date from URL.

    Args:
        url: Article URL

    Returns:
        datetime if date found, None otherwise
    """
    if not url:
        return None

    # Try Unix timestamp first (most reliable when present)
    timestamp_match = UNIX_TIMESTAMP_PATTERN.search(url)
    if timestamp_match:
        timestamp_str = timestamp_match.group(1) or timestamp_match.group(2)
        try:
            timestamp = int(timestamp_str)
            # 13-digit = milliseconds, 10-digit = seconds
            if len(timestamp_str) == 13:
                timestamp = timestamp // 1000

            # Sanity check: should be between 2000 and 2030
            dt = datetime.utcfromtimestamp(timestamp)
            if 2000 <= dt.year <= 2030:
                logger.debug(f"Extracted Unix timestamp from URL: {dt}")
                return dt
        except (ValueError, OSError):
            pass

    # Try date patterns
    for pattern, pattern_type in URL_DATE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            try:
                groups = match.groups()

                if pattern_type == "ymd_slash" or pattern_type == "ymd_dash" or pattern_type == "ymd_compact":
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                elif pattern_type == "dmy_dash":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                elif pattern_type == "mdy_dash":
                    month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                elif pattern_type == "ym_only":
                    year, month = int(groups[0]), int(groups[1])
                    day = 1  # Default to first of month
                else:
                    continue

                # Validate date components
                if not (2000 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
                    continue

                dt = datetime(year, month, day)
                logger.debug(f"Extracted date from URL ({pattern_type}): {dt}")
                return dt

            except (ValueError, IndexError):
                continue

    return None


def validate_article_recency(
    url: str,
    seendate: datetime,
    max_age_hours: int = 48,
    max_discrepancy_hours: int = 72,
) -> tuple[bool, str, datetime | None]:
    """
    Validate article recency by comparing URL date with seendate.

    Args:
        url: Article URL
        seendate: GDELT seendate (when article was indexed)
        max_age_hours: Maximum allowed age from current time
        max_discrepancy_hours: Maximum allowed discrepancy between URL date and seendate

    Returns:
        Tuple of (is_valid, reason, url_date)
        - is_valid: True if article passes recency check
        - reason: Explanation of the decision
        - url_date: Extracted URL date (if any)
    """
    current_time = datetime.utcnow()
    url_date = extract_date_from_url(url)

    # If we have a URL date, use it as primary source
    if url_date:
        url_age_hours = (current_time - url_date).total_seconds() / 3600

        # Check if URL date is too old
        if url_age_hours > max_age_hours:
            return (
                False,
                f"URL_DATE_TOO_OLD: {url_age_hours:.1f}h (max: {max_age_hours}h)",
                url_date,
            )

        # Check discrepancy between URL date and seendate
        discrepancy_hours = abs((seendate - url_date).total_seconds()) / 3600
        if discrepancy_hours > max_discrepancy_hours:
            return (
                False,
                f"DATE_DISCREPANCY: URL={url_date.date()}, seen={seendate.date()} "
                f"(diff: {discrepancy_hours:.1f}h)",
                url_date,
            )

        return (
            True,
            f"URL_DATE_VALID: {url_date.date()} (age: {url_age_hours:.1f}h)",
            url_date,
        )

    # No URL date - fall back to seendate only
    seendate_age_hours = (current_time - seendate).total_seconds() / 3600

    if seendate_age_hours > max_age_hours:
        return (
            False,
            f"SEENDATE_TOO_OLD: {seendate_age_hours:.1f}h (max: {max_age_hours}h)",
            None,
        )

    return (
        True,
        f"SEENDATE_ONLY: {seendate.date()} (age: {seendate_age_hours:.1f}h, no URL date)",
        None,
    )


def extract_all_dates_from_url(url: str) -> list[dict]:
    """
    Extract all possible dates from URL (for debugging).

    Returns list of dicts with pattern info and extracted date.
    """
    results = []

    # Unix timestamp
    timestamp_match = UNIX_TIMESTAMP_PATTERN.search(url)
    if timestamp_match:
        timestamp_str = timestamp_match.group(1) or timestamp_match.group(2)
        try:
            timestamp = int(timestamp_str)
            if len(timestamp_str) == 13:
                timestamp = timestamp // 1000
            dt = datetime.utcfromtimestamp(timestamp)
            if 2000 <= dt.year <= 2030:
                results.append({
                    "pattern": "unix_timestamp",
                    "match": timestamp_str,
                    "date": dt,
                })
        except (ValueError, OSError):
            pass

    # Date patterns
    for pattern, pattern_type in URL_DATE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            results.append({
                "pattern": pattern_type,
                "match": match.group(0),
                "groups": match.groups(),
            })

    return results


# ============================================
# Content-based Date Extraction (Layer 2)
# ============================================

# Date patterns in content (ordered by specificity)
CONTENT_DATE_PATTERNS = [
    # "October 15, 2023" or "October 15 2023"
    (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', "month_day_year"),
    # "15 October 2023"
    (r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', "day_month_year"),
    # "Oct 15, 2023" or "Oct. 15, 2023"
    (r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b', "abbr_month_day_year"),
    # "2023-10-15" or "2023/10/15"
    (r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', "iso_date"),
    # "on January 6, 2021" (with preposition context)
    (r'\bon\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', "on_date"),
]

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Past year detection pattern (2020-2025, current year excluded)
PAST_YEAR_PATTERN = re.compile(r'\b(20[0-2][0-9])\b')


def extract_date_from_content(title: str, content: str = "") -> datetime | None:
    """
    Extract publication/event date from article title or content.

    Looks for explicit date mentions like:
    - "October 15, 2023"
    - "15 October 2023"
    - "2023-10-15"
    - "on January 6, 2021"

    Args:
        title: Article title
        content: Article content/body (optional)

    Returns:
        datetime if date found, None otherwise
    """
    # Combine title and content (title has priority)
    text = f"{title} {content[:1000]}" if content else title

    for pattern, pattern_type in CONTENT_DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()

                if pattern_type in ("month_day_year", "abbr_month_day_year", "on_date"):
                    month_str = groups[0].lower()
                    day = int(groups[1])
                    year = int(groups[2])
                    month = MONTH_MAP.get(month_str, 0)
                elif pattern_type == "day_month_year":
                    day = int(groups[0])
                    month_str = groups[1].lower()
                    year = int(groups[2])
                    month = MONTH_MAP.get(month_str, 0)
                elif pattern_type == "iso_date":
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                else:
                    continue

                # Validate date components
                if not (2000 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
                    continue

                dt = datetime(year, month, day)
                logger.debug(f"Extracted date from content ({pattern_type}): {dt}")
                return dt

            except (ValueError, IndexError, KeyError):
                continue

    return None


def contains_past_year(text: str, current_year: int | None = None) -> tuple[bool, int | None]:
    """
    Check if text explicitly mentions a past year.

    Used to detect old events being reported as current news.

    Examples:
        "October 15, 2023 attack" → (True, 2023)
        "Breaking news today" → (False, None)
        "In 2021, the incident..." → (True, 2021)

    Args:
        text: Text to search
        current_year: Current year (defaults to CURRENT_YEAR)

    Returns:
        Tuple of (has_past_year, year)
    """
    if current_year is None:
        current_year = CURRENT_YEAR

    matches = PAST_YEAR_PATTERN.findall(text)

    for year_str in matches:
        year = int(year_str)
        # Check if it's a past year (not current year)
        if year < current_year:
            return (True, year)

    return (False, None)


def validate_trigger_recency(
    url: str,
    title: str,
    content: str = "",
    api_date: datetime | None = None,
    max_age_hours: int = 48,
) -> tuple[bool, str, datetime | None]:
    """
    Validate trigger event recency using 4-Layer validation.

    Layer 1: URL date patterns (most reliable)
    Layer 2: Content date extraction (title/body explicit dates)
    Layer 3: Past year detection (catch old events)
    Layer 4: API-provided date (fallback, may be unreliable)

    IMPORTANT: This is stricter than validate_article_recency().
    If content mentions a past year, the event is rejected.

    Args:
        url: Article URL
        title: Article title
        content: Article content/body
        api_date: API-provided date (seendate, created_utc, etc.)
        max_age_hours: Maximum allowed age from current time

    Returns:
        Tuple of (is_valid, reason, validated_date)
        - is_valid: True if event passes recency check
        - reason: Explanation of the decision
        - validated_date: The validated datetime to use
    """
    current_time = datetime.utcnow()
    current_year = current_time.year

    # Layer 1: URL date extraction
    url_date = extract_date_from_url(url)
    if url_date:
        url_age_hours = (current_time - url_date).total_seconds() / 3600

        if url_age_hours > max_age_hours:
            return (
                False,
                f"URL_DATE_TOO_OLD: {url_date.date()} (age: {url_age_hours:.1f}h)",
                url_date,
            )

        # URL date is valid and recent
        logger.debug(f"Layer 1 (URL): Valid date {url_date.date()}")
        return (
            True,
            f"URL_DATE_VALID: {url_date.date()} (age: {url_age_hours:.1f}h)",
            url_date,
        )

    # Layer 2: Content date extraction
    content_date = extract_date_from_content(title, content)
    if content_date:
        content_age_hours = (current_time - content_date).total_seconds() / 3600

        if content_age_hours > max_age_hours:
            return (
                False,
                f"CONTENT_DATE_TOO_OLD: {content_date.date()} (age: {content_age_hours:.1f}h)",
                content_date,
            )

        # Content date is valid and recent
        logger.debug(f"Layer 2 (Content): Valid date {content_date.date()}")
        return (
            True,
            f"CONTENT_DATE_VALID: {content_date.date()} (age: {content_age_hours:.1f}h)",
            content_date,
        )

    # Layer 3: Past year detection (CRITICAL)
    full_text = f"{title} {content}"
    has_past_year, past_year = contains_past_year(full_text, current_year)
    if has_past_year:
        return (
            False,
            f"PAST_YEAR_DETECTED: Article mentions year {past_year} (current: {current_year})",
            None,
        )

    # Layer 4: API-provided date (fallback)
    if api_date:
        api_age_hours = (current_time - api_date).total_seconds() / 3600

        if api_age_hours > max_age_hours:
            return (
                False,
                f"API_DATE_TOO_OLD: {api_date.date()} (age: {api_age_hours:.1f}h)",
                api_date,
            )

        # API date is valid, but warn that no URL/content date was found
        logger.debug(f"Layer 4 (API): Using API date {api_date.date()} (no content validation)")
        return (
            True,
            f"API_DATE_ONLY: {api_date.date()} (age: {api_age_hours:.1f}h, no content date found)",
            api_date,
        )

    # No date information at all - conservative rejection
    return (
        False,
        "NO_DATE_INFO: Unable to determine article date (URL, content, API all failed)",
        None,
    )
