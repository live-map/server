"""
Social media tools for investigation agent.

- search_telegram: Telegram channel search
- search_youtube: YouTube video search
"""

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


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
async def search_telegram(query: str, channel: str | None = None) -> list[dict]:
    """
    Search messages from Telegram channels.

    Note: Only searches from subscribed channels.
    If the agent needs a specific channel, specify the channel name.

    Examples:
    - query="Iran protest", channel="IranIntl"
    - query="Ukraine attack", channel="ukrainenowenglish"
    - query="OSINT footage", channel="GeoConfirmed"

    Suggested channels:
    {suggested_channels}

    Args:
        query: Search query
        channel: Specific channel name (searches all subscribed channels if None)

    Returns:
        Message list [{text, date, channel, media_type, media_url}]
    """.format(suggested_channels=SUGGESTED_TELEGRAM_CHANNELS)

    # TODO: Actual Telethon integration needed
    # Currently a placeholder

    return [{
        "status": "telegram_not_configured",
        "message": "Telegram search requires Telethon configuration with API credentials",
        "suggested_action": f"To search for '{query}'" + (f" in @{channel}" if channel else "") + ", configure TELEGRAM_API_ID and TELEGRAM_API_HASH",
        "suggested_channels": [
            "ukrainenowenglish", "nexta_live", "IranIntl",
            "GeoConfirmed", "WarMonitor3"
        ]
    }]


@tool
async def search_youtube(query: str, max_results: int = 10) -> list[dict]:
    """
    Search videos on YouTube.

    Use this to find protest, war, and conflict-related videos.
    Include region, date, event in search query to improve accuracy.

    Examples:
    - "Tehran protest 2026" -> Tehran protest videos
    - "Ukraine war footage Kharkiv" -> Kharkiv war footage
    - "Syria airstrike video" -> Syria airstrike videos

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        Video list [{title, video_id, url, channel, published, thumbnail}]
    """
    try:
        # YouTube search results page URL
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

        return [{
            "status": "youtube_search_available",
            "search_url": search_url,
            "query": query,
            "note": "YouTube API key required for detailed results. Use get_video_info for specific videos.",
            "manual_search_url": search_url,
        }]

    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return [{"error": str(e)}]
