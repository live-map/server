"""
Search tools for investigation agent.

Priority-based search strategy (based on expert research):
1. GDELT (free) - News/events specialized
2. DuckDuckGo News (free) - Recent news search
3. DuckDuckGo Web (free) - General web search (filtered)
4. Tavily (paid) - High-quality fallback

- search_news_gdelt: GDELT news search (FREE, news specialized)
- search_news_ddg: DuckDuckGo NEWS search (FREE, recent news only)
- search_web_free: DuckDuckGo search (FREE, general web, filtered)
- search_web: Tavily-based web search (PAID, high quality)
"""

import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool

from app.agent.config import agent_settings

logger = logging.getLogger(__name__)

# =============================================================================
# DOMAINS TO EXCLUDE FROM EVIDENCE (not news sources)
# =============================================================================
EXCLUDED_DOMAINS = {
    # Wikipedia and wikis
    "wikipedia.org",
    "en.wikipedia.org",
    "ko.wikipedia.org",
    "wikidata.org",
    "wikimedia.org",
    "wikiwand.com",
    # Reference sites (not news)
    "britannica.com",
    "dictionary.com",
    "merriam-webster.com",
    "encyclopedia.com",
    # Social media (not primary sources)
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "reddit.com",
    # Academic/archive (old content)
    "jstor.org",
    "archive.org",
    "academia.edu",
    "researchgate.net",
}


def _is_valid_url(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def _extract_domain(url: str) -> str:
    """Safely extract domain from URL."""
    if not url:
        return "unknown"
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "") or "unknown"
    except Exception:
        return "unknown"


def _is_excluded_domain(url: str) -> bool:
    """Check if URL is from an excluded domain (Wikipedia, etc.)."""
    if not url:
        return True
    try:
        domain = _extract_domain(url).lower()
        for excluded in EXCLUDED_DOMAINS:
            if excluded in domain:
                return True
        return False
    except Exception:
        return False


def _extract_date_from_url(url: str) -> datetime | None:
    """Extract date from URL if present (common in news URLs)."""
    if not url:
        return None

    # Common patterns: /2024/01/23/, /2024-01-23/, /20240123/
    patterns = [
        r'/(\d{4})/(\d{2})/(\d{2})/',  # /2024/01/23/
        r'/(\d{4})-(\d{2})-(\d{2})/',  # /2024-01-23/
        r'/(\d{4})(\d{2})(\d{2})/',     # /20240123/
        r'/(\d{4})/(\d{2})/',           # /2024/01/ (month only)
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            try:
                groups = match.groups()
                year = int(groups[0])
                month = int(groups[1])
                day = int(groups[2]) if len(groups) > 2 else 1
                return datetime(year, month, day)
            except (ValueError, IndexError):
                continue
    return None


def _is_recent_url(url: str, max_age_days: int = 7) -> bool:
    """Check if URL appears to be recent based on date in URL."""
    url_date = _extract_date_from_url(url)
    if url_date is None:
        # Can't determine date, don't filter
        return True

    cutoff = datetime.now() - timedelta(days=max_age_days)
    return url_date >= cutoff


# =============================================================================
# FREE SEARCH TOOLS (Use these first!)
# =============================================================================


@tool
async def search_news_ddg(query: str, max_results: int = 15, max_age_days: int = 7) -> list[dict]:
    """
    FREE news search using DuckDuckGo News. Use for RECENT news only.

    This searches DuckDuckGo's news index which only returns recent articles.
    Use this for evidence gathering on current events.

    Args:
        query: Search query (news topics, events, breaking news)
        max_results: Maximum number of results (default 15)
        max_age_days: Maximum age of articles in days (default 7)

    Returns:
        List of news results [{title, url, content, source, source_name, published}]
    """
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            # Use news() instead of text() for recent news only
            for r in ddgs.news(query, max_results=max_results):
                url = r.get("url", r.get("link", ""))

                # Validate URL
                if not _is_valid_url(url):
                    logger.debug(f"Skipping invalid URL: {url}")
                    continue

                # Filter out excluded domains (Wikipedia, etc.)
                if _is_excluded_domain(url):
                    logger.debug(f"Skipping excluded domain: {url}")
                    continue

                # Filter by URL date if present
                if not _is_recent_url(url, max_age_days=max_age_days):
                    logger.debug(f"Skipping old URL: {url}")
                    continue

                domain = _extract_domain(url)
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("body", "")[:500],
                    "source": domain,
                    "source_name": f"DDGNews:{domain}",
                    "published": r.get("date", ""),
                })

        logger.info(f"DuckDuckGo News: {len(results)} articles for '{query[:30]}...'")
        return results

    except Exception as e:
        logger.error(f"DuckDuckGo News search error: {e}")
        return []  # Return empty list on error


@tool
async def search_web_free(query: str, max_results: int = 10, filter_old: bool = True) -> list[dict]:
    """
    FREE web search using DuckDuckGo. Use this BEFORE paid search tools.

    This is a free alternative to Tavily. Always try this first for general
    web searches to save costs.

    NOTE: This returns general web results. For news/evidence gathering,
    prefer search_news_ddg or search_news_gdelt.

    Args:
        query: Search query (any topic, news, general information)
        max_results: Maximum number of results (default 10)
        filter_old: Filter out Wikipedia and old URLs (default True)

    Returns:
        List of results [{title, url, content, source, source_name}]
    """
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results * 2):  # Fetch more to account for filtering
                # New ddgs package uses 'link' instead of 'href'
                url = r.get("link", r.get("href", ""))

                # Validate URL
                if not _is_valid_url(url):
                    logger.debug(f"Skipping invalid URL: {url}")
                    continue

                # Filter out excluded domains (Wikipedia, etc.)
                if filter_old and _is_excluded_domain(url):
                    logger.debug(f"Skipping excluded domain: {url}")
                    continue

                # Filter by URL date if present
                if filter_old and not _is_recent_url(url, max_age_days=30):
                    logger.debug(f"Skipping old URL: {url}")
                    continue

                domain = _extract_domain(url)
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("body", "")[:500],
                    "source": domain,
                    "source_name": f"DuckDuckGo:{domain}",
                })

                if len(results) >= max_results:
                    break

        logger.info(f"DuckDuckGo: {len(results)} results for '{query[:30]}...'")
        return results

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []  # Return empty list on error


# =============================================================================
# PAID SEARCH TOOLS (Use as fallback when free tools are insufficient)
# =============================================================================


@tool
async def search_web(query: str, max_results: int = 10) -> list[dict]:
    """
    PAID high-quality web search using Tavily. Use ONLY when free tools fail.

    This is a premium search tool with better accuracy (93.3% on benchmarks).
    IMPORTANT: Only use this when search_web_free or search_news_gdelt
    return insufficient results.

    Args:
        query: Search query (freely combine source names, keywords, regions)
        max_results: Maximum number of results (default 10)

    Returns:
        List of results [{title, url, content, source}]
    """
    if not agent_settings.tavily_api_key:
        logger.warning("Tavily API key not configured")
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": agent_settings.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": max_results,
                    "include_answer": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("results", []):
                url = r.get("url", "")

                # Validate URL
                if not _is_valid_url(url):
                    continue

                domain = _extract_domain(url)
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("content", "")[:500],
                    "source": domain,
                    "source_name": f"Tavily:{domain}",
                    "score": r.get("score", 0),
                })

            logger.info(f"Tavily: {len(results)} results for '{query[:30]}...'")
            return results

    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return []  # Return empty list on error


# =============================================================================
# NEWS-SPECIFIC TOOLS (Use for breaking news and events)
# =============================================================================


@tool
async def search_news_gdelt(query: str, timespan: str = "24h", max_results: int = 20) -> list[dict]:
    """
    FREE global news search from GDELT. PRIMARY tool for news/events.

    ALWAYS use this FIRST for breaking news, conflicts, protests, disasters.
    Covers 100,000+ news sources worldwide in 100+ languages.

    Examples:
    - "Iran protest Tehran" -> Global coverage on Tehran protests
    - "Ukraine war Kharkiv" -> Coverage on Kharkiv war
    - "Syria airstrike" -> Coverage on Syria airstrikes

    Args:
        query: Search query (keywords, locations, topics)
        timespan: Search period (1h, 6h, 12h, 24h, 48h, 72h)
        max_results: Maximum number of results

    Returns:
        News list [{title, url, source, published, language, country}]
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params={
                    "query": query,
                    "mode": "artlist",
                    "maxrecords": str(max_results),
                    "format": "json",
                    "timespan": timespan,
                    "sort": "datedesc",
                },
            )

            # 응답 상태 체크
            if response.status_code != 200:
                logger.warning(f"GDELT returned status {response.status_code}")
                return []

            # 응답 내용 체크 (빈 응답 또는 HTML 반환 시)
            content = response.text
            if not content or content.startswith("<!") or content.startswith("<html"):
                logger.warning(f"GDELT returned non-JSON response")
                return []

            try:
                data = response.json()
            except Exception as json_err:
                logger.warning(f"GDELT JSON parse error: {json_err}")
                return []

            results = []
            for art in data.get("articles", []):
                url = art.get("url", "")

                # Validate URL
                if not _is_valid_url(url):
                    continue

                domain = _extract_domain(url)
                results.append({
                    "title": art.get("title", ""),
                    "url": url,
                    "source": domain,
                    "source_name": f"GDELT:{domain}",
                    "content": art.get("title", ""),  # GDELT은 content가 없어서 title 사용
                    "published": art.get("seendate", ""),
                    "language": art.get("language", ""),
                    "country": art.get("sourcecountry", ""),
                })

            logger.info(f"GDELT: {len(results)} articles for '{query[:30]}...'")
            return results

    except httpx.TimeoutException:
        logger.warning("GDELT request timed out")
        return []
    except Exception as e:
        logger.error(f"GDELT search error: {e}")
        return []
