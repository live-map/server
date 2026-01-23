"""
URL Date Extractor - Extract publication dates from news article URLs

Many news websites include publication dates in their URLs:
- /2026/01/23/article-title
- /2026-01-23/article
- /news/20260123-article
- Unix timestamps: /news/article-1769158862.html

This module extracts these dates and compares with GDELT seendate
to detect stale/old articles being re-indexed.
"""

import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

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
