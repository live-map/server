"""
Social media tools for investigation agent.

- search_telegram: Telegram channel search
- search_youtube: YouTube video search
"""

import logging
from datetime import datetime, timezone

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Maximum age for social media content (30 days)
MAX_AGE_DAYS = 30


def _is_recent_published_date(published_at: str, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """
    Check if published date is within the maximum age limit.

    Args:
        published_at: ISO 8601 date string (e.g., "2026-01-20T12:00:00Z")
        max_age_days: Maximum age in days

    Returns:
        True if the content is recent enough, False otherwise
    """
    if not published_at:
        # Can't determine date, allow by default
        return True

    try:
        # Handle various ISO formats
        published_at = published_at.replace("Z", "+00:00")
        pub_date = datetime.fromisoformat(published_at)

        # Make sure we have timezone-aware datetime
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_days = (now - pub_date).days

        if age_days > max_age_days:
            logger.debug(f"Skipping old content from {published_at} ({age_days} days old)")
            return False

        return True

    except (ValueError, TypeError) as e:
        logger.debug(f"Could not parse date {published_at}: {e}")
        # Can't parse, allow by default
        return True


# Suggested Telegram channels for reference
SUGGESTED_TELEGRAM_CHANNELS = """
Channels the agent can search (requires subscription):

Ukraine/Russia:
- @ukrainenowenglish - Ukraine official English channel
- @nexta_live - Eastern Europe news
- @KyivIndependent - Kyiv Independent
- @intelslava - Russian OSINT

Iran/Middle East:
- @IranIntl - Iran International
- @IranHRM - Iran Human Rights
- @AJABreaking - Al Jazeera Breaking

OSINT:
- @GeoConfirmed - Geolocation verification
- @WarMonitor3 - War monitoring

Note: Actual search is only possible from subscribed channels.
"""


@tool
async def search_telegram(query: str, channel: str | None = None, max_age_days: int = MAX_AGE_DAYS) -> list[dict]:
    """
    Search messages from Telegram channels.

    Note: Only searches from subscribed channels.
    If the agent needs a specific channel, specify the channel name.

    NOTE: Telegram messages are real-time, but messages older than 30 days
    (configurable) will be filtered for evidence freshness.

    Examples:
    - query="Iran protest", channel="IranIntl"
    - query="Ukraine attack", channel="ukrainenowenglish"
    - query="OSINT footage", channel="GeoConfirmed"

    Suggested channels for different regions:
    - Ukraine/Russia: @ukrainenowenglish, @nexta_live, @KyivIndependent
    - Iran/Middle East: @IranIntl, @IranHRM, @AJABreaking
    - OSINT: @GeoConfirmed, @WarMonitor3

    Args:
        query: Search query
        channel: Specific channel name (searches all subscribed channels if None)
        max_age_days: Maximum message age in days (default 30)

    Returns:
        Message list [{text, date, channel, media_type, media_url}]
    """

    # TODO: Actual Telethon integration needed
    # When implemented:
    # - Fetch messages with date field
    # - Filter using: if not _is_recent_published_date(msg["date"], max_age_days): continue

    return [{
        "status": "telegram_not_configured",
        "message": "Telegram search requires Telethon configuration with API credentials",
        "suggested_action": f"To search for '{query}'" + (f" in @{channel}" if channel else "") + ", configure TELEGRAM_API_ID and TELEGRAM_API_HASH",
        "suggested_channels": [
            "ukrainenowenglish", "nexta_live", "IranIntl",
            "GeoConfirmed", "WarMonitor3"
        ],
        "note": f"Messages older than {max_age_days} days will be filtered when enabled."
    }]


@tool
async def search_youtube(query: str, max_results: int = 10, max_age_days: int = MAX_AGE_DAYS) -> list[dict]:
    """
    Search videos on YouTube.

    Use this to find protest, war, and conflict-related videos.
    Include region, date, event in search query to improve accuracy.

    NOTE: Only returns videos published within the last 30 days (configurable).

    Examples:
    - "Tehran protest 2026" -> Tehran protest videos
    - "Ukraine war footage Kharkiv" -> Kharkiv war footage
    - "Syria airstrike video" -> Syria airstrike videos

    Args:
        query: Search query
        max_results: Maximum number of results
        max_age_days: Maximum video age in days (default 30)

    Returns:
        Video list [{title, video_id, url, channel, published, thumbnail}]
    """
    try:
        # YouTube search results page URL
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

        # TODO: When YouTube Data API is integrated:
        # - Fetch videos with publishedAt field
        # - Filter using: if not _is_recent_published_date(video["publishedAt"], max_age_days): continue

        return [{
            "status": "youtube_search_available",
            "search_url": search_url,
            "query": query,
            "note": f"YouTube API key required for detailed results. Videos older than {max_age_days} days will be filtered.",
            "manual_search_url": search_url,
        }]

    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return [{"error": str(e)}]
