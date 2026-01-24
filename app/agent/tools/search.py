"""
Search tools for investigation agent.

Priority-based search strategy (based on expert research):
1. GDELT (free) - News/events specialized
2. DuckDuckGo News (free) - Recent news search
3. Brave Search (free tier) - P1 Enhancement
4. DuckDuckGo Web (free) - General web search (filtered)
5. Tavily (paid) - High-quality fallback

- search_news_gdelt: GDELT news search (FREE, news specialized)
- search_news_ddg: DuckDuckGo NEWS search (FREE, recent news only)
- search_news_brave: Brave Search NEWS (FREE tier, 2000 queries/month)
- search_web_free: DuckDuckGo search (FREE, general web, filtered)
- search_web: Tavily-based web search (PAID, high quality)
- search_multi: P1 - Parallel search across multiple engines

P1 Enhancement:
- Non-English query translation support
- Multi-engine parallel search
- Response caching (15 min TTL)
- Brave Search integration
"""

import asyncio
import hashlib
import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from dateutil.parser import parse as parse_date
from langchain_core.tools import tool

from app.agent.config import agent_settings

logger = logging.getLogger(__name__)


# =============================================================================
# P2: SEARCH ERROR TRACKING
# =============================================================================
# Tracks recent search errors to distinguish "no results" from "API failure"

from dataclasses import dataclass, field
from enum import Enum


class SearchErrorType(Enum):
    """Type of search error for better debugging."""
    NONE = "none"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"


@dataclass
class SearchStats:
    """Track search statistics for debugging."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    empty_results: int = 0
    errors_by_type: dict = field(default_factory=dict)

    def record_success(self, result_count: int):
        self.total_queries += 1
        self.successful_queries += 1
        if result_count == 0:
            self.empty_results += 1

    def record_error(self, error_type: SearchErrorType, error_msg: str):
        self.total_queries += 1
        self.failed_queries += 1
        type_name = error_type.value
        if type_name not in self.errors_by_type:
            self.errors_by_type[type_name] = []
        # Keep last 10 errors per type
        self.errors_by_type[type_name].append(error_msg[:100])
        if len(self.errors_by_type[type_name]) > 10:
            self.errors_by_type[type_name] = self.errors_by_type[type_name][-10:]


# Global search stats tracker
_search_stats: dict[str, SearchStats] = {}


def get_search_stats(tool_name: str) -> SearchStats:
    """Get search stats for a tool."""
    if tool_name not in _search_stats:
        _search_stats[tool_name] = SearchStats()
    return _search_stats[tool_name]


def get_all_search_stats() -> dict:
    """Get all search stats for debugging."""
    return {name: {
        "total": stats.total_queries,
        "success": stats.successful_queries,
        "failed": stats.failed_queries,
        "empty": stats.empty_results,
        "error_types": list(stats.errors_by_type.keys()),
    } for name, stats in _search_stats.items()}


# =============================================================================
# P1: SEARCH RESULT CACHING (15 min TTL)
# =============================================================================

# Cache structure: {cache_key: (timestamp, results)}
_search_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes (increased from 5 min)


def _get_cache_key(tool_name: str, query: str, **kwargs) -> str:
    """Generate cache key for search query."""
    key_data = f"{tool_name}:{query}:{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()


def _get_cached_results(cache_key: str) -> list[dict] | None:
    """Get cached search results if valid."""
    cached = _search_cache.get(cache_key)
    if cached:
        timestamp, results = cached
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            logger.debug(f"Cache hit for {cache_key[:8]}...")
            return results
    return None


def _set_cached_results(cache_key: str, results: list[dict]) -> None:
    """Cache search results."""
    _search_cache[cache_key] = (time.time(), results)
    _cleanup_cache()


def _cleanup_cache() -> None:
    """Remove expired cache entries."""
    current_time = time.time()
    expired_keys = [
        k for k, (ts, _) in _search_cache.items()
        if current_time - ts > CACHE_TTL_SECONDS
    ]
    for k in expired_keys:
        del _search_cache[k]


# =============================================================================
# NON-ENGLISH QUERY TRANSLATION (P1 Enhancement)
# =============================================================================

# P1 Fix: Translation cache to avoid re-translating the same query
# Structure: {query_hash: (timestamp, translated_query)}
_translation_cache: dict[str, tuple[float, str]] = {}
TRANSLATION_CACHE_TTL = 3600  # 1 hour


def _get_translation_cache_key(query: str, source_lang: str) -> str:
    """Generate cache key for translation."""
    return hashlib.md5(f"{query}:{source_lang}".encode()).hexdigest()


def _get_cached_translation(query: str, source_lang: str) -> str | None:
    """Get cached translation if valid."""
    cache_key = _get_translation_cache_key(query, source_lang)
    cached = _translation_cache.get(cache_key)
    if cached:
        timestamp, translated = cached
        if time.time() - timestamp < TRANSLATION_CACHE_TTL:
            logger.debug(f"Translation cache hit: '{query[:30]}...'")
            return translated
    return None


def _set_cached_translation(query: str, source_lang: str, translated: str) -> None:
    """Cache translation result."""
    cache_key = _get_translation_cache_key(query, source_lang)
    _translation_cache[cache_key] = (time.time(), translated)
    # Cleanup old entries (keep max 100)
    if len(_translation_cache) > 100:
        oldest_key = min(_translation_cache.keys(), key=lambda k: _translation_cache[k][0])
        del _translation_cache[oldest_key]


def _is_non_latin(text: str) -> bool:
    """Check if text contains non-Latin characters (Korean, Chinese, Arabic, etc.)."""
    for char in text:
        if char.isalpha():
            # Get the Unicode category/script
            name = unicodedata.name(char, "")
            if any(script in name for script in [
                "HANGUL", "CJK", "HIRAGANA", "KATAKANA",
                "ARABIC", "CYRILLIC", "THAI", "HEBREW"
            ]):
                return True
    return False


def _detect_language(text: str) -> str:
    """Simple language detection based on character analysis.

    Returns:
        ISO 639-1 language code (ko, zh, ja, ar, ru, th, he, en)
    """
    hangul_count = 0
    cjk_count = 0
    hiragana_count = 0
    arabic_count = 0
    cyrillic_count = 0
    total_alpha = 0

    for char in text:
        if char.isalpha():
            total_alpha += 1
            name = unicodedata.name(char, "")
            if "HANGUL" in name:
                hangul_count += 1
            elif "CJK" in name:
                cjk_count += 1
            elif "HIRAGANA" in name or "KATAKANA" in name:
                hiragana_count += 1
            elif "ARABIC" in name:
                arabic_count += 1
            elif "CYRILLIC" in name:
                cyrillic_count += 1

    if total_alpha == 0:
        return "en"

    # Determine dominant script
    threshold = 0.3  # 30% of characters
    if hangul_count / total_alpha > threshold:
        return "ko"
    if cjk_count / total_alpha > threshold:
        return "zh"
    if hiragana_count / total_alpha > threshold:
        return "ja"
    if arabic_count / total_alpha > threshold:
        return "ar"
    if cyrillic_count / total_alpha > threshold:
        return "ru"

    return "en"


async def _translate_query(query: str, source_lang: str = "auto") -> str:
    """
    Translate non-English query to English for better search results.

    P1 Fix: Now caches translation results to avoid redundant API calls
    when the same query is used for multiple search engines.

    Uses free translation services. Falls back to original query on failure.

    Args:
        query: Search query to translate
        source_lang: Source language code (auto-detect if "auto")

    Returns:
        Translated query in English, or original query on failure
    """
    # Detect language if auto
    if source_lang == "auto":
        source_lang = _detect_language(query)

    # Skip if already English
    if source_lang == "en" or not _is_non_latin(query):
        return query

    # P1 Fix: Check translation cache first
    cached = _get_cached_translation(query, source_lang)
    if cached is not None:
        return cached

    try:
        # Use LibreTranslate API (free, self-hosted available)
        # Fallback: Use Google Translate's unofficial endpoint
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try LibreTranslate first (if configured)
            libre_url = agent_settings.libre_translate_url if hasattr(agent_settings, 'libre_translate_url') else None

            if libre_url:
                response = await client.post(
                    f"{libre_url}/translate",
                    json={
                        "q": query,
                        "source": source_lang,
                        "target": "en",
                        "format": "text",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("translatedText", query)
                    logger.info(f"Translated '{query}' -> '{translated}' ({source_lang} -> en)")
                    # Cache the translation
                    _set_cached_translation(query, source_lang, translated)
                    return translated

            # Fallback: Use MyMemory Translation API (free, 1000 chars/day)
            response = await client.get(
                "https://api.mymemory.translated.net/get",
                params={
                    "q": query[:500],  # Limit to 500 chars
                    "langpair": f"{source_lang}|en",
                },
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("responseStatus") == 200:
                    translated = data.get("responseData", {}).get("translatedText", query)
                    # Clean up potential HTML entities
                    translated = translated.replace("&#39;", "'").replace("&quot;", '"')
                    logger.info(f"Translated '{query}' -> '{translated}' ({source_lang} -> en)")
                    # Cache the translation
                    _set_cached_translation(query, source_lang, translated)
                    return translated

    except Exception as e:
        logger.warning(f"Translation failed for '{query}': {e}")

    # Return original query on failure (also cache the failure)
    _set_cached_translation(query, source_lang, query)
    return query


async def _prepare_search_query(query: str, translate: bool = True) -> str:
    """
    Prepare search query for optimal results.

    1. Detect language
    2. Translate if non-English
    3. Clean up query

    Args:
        query: Original search query
        translate: Whether to translate non-English queries

    Returns:
        Prepared query string
    """
    if not translate:
        return query

    # Translate if non-Latin characters detected
    if _is_non_latin(query):
        translated = await _translate_query(query)
        # Return both translated and original for broader results
        if translated != query:
            return f"{translated} OR {query}"

    return query

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


def _parse_published_date(date_str: str) -> datetime | None:
    """
    Parse published date from API response.

    Handles various formats:
    - ISO 8601: "2026-01-23T15:30:00Z"
    - Human readable: "Jan 23, 2026"
    - Relative: "2 hours ago" (via dateutil fuzzy parsing)
    - GDELT seendate: "20260123T153000Z"

    Returns:
        datetime object if parsing succeeds, None otherwise.
    """
    if not date_str:
        return None
    try:
        return parse_date(date_str, fuzzy=True)
    except Exception:
        return None


def _is_evidence_recent(doc: dict, max_age_days: int = 30) -> bool:
    """
    Check if evidence document is recent using 3-layer validation.

    Layer 1: API published date field (GDELT seendate, DDG date)
    Layer 2: URL date pattern extraction
    Layer 3: No date info → REJECT (conservative approach)

    Args:
        doc: Evidence document with url, published fields
        max_age_days: Maximum age in days (default 30)

    Returns:
        True if document is recent, False otherwise
    """
    url = doc.get("url", "")

    # Layer 1: Check API published date field
    published = doc.get("published", "")
    pub_date = _parse_published_date(published)

    if pub_date:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        is_recent = pub_date >= cutoff
        if not is_recent:
            logger.debug(f"Rejected by published date ({published}): {url[:60]}...")
        return is_recent

    # Layer 2: Extract date from URL pattern
    url_date = _extract_date_from_url(url)

    if url_date:
        cutoff = datetime.now() - timedelta(days=max_age_days)
        is_recent = url_date >= cutoff
        if not is_recent:
            logger.debug(f"Rejected by URL date: {url[:60]}...")
        return is_recent

    # Layer 3: No date info → REJECT (conservative approach)
    # This prevents old articles without dates from being used as evidence
    logger.warning(f"No date info found - REJECTING: {url[:60]}...")
    return False


# =============================================================================
# FREE SEARCH TOOLS (Use these first!)
# =============================================================================


@tool
async def search_news_ddg(
    query: str,
    max_results: int = 15,
    max_age_days: int = 7,
    translate_query: bool = True,
) -> list[dict]:
    """
    FREE news search using DuckDuckGo News. Use for RECENT news only.

    This searches DuckDuckGo's news index which only returns recent articles.
    Use this for evidence gathering on current events.

    P1 Enhancement: Automatically translates non-English queries for better results.

    Args:
        query: Search query (news topics, events, breaking news)
        max_results: Maximum number of results (default 15)
        max_age_days: Maximum age of articles in days (default 7)
        translate_query: Whether to translate non-English queries (default True)

    Returns:
        List of news results [{title, url, content, source, source_name, published}]
    """
    try:
        from ddgs import DDGS

        # P1: Translate query if needed
        search_query = await _prepare_search_query(query, translate=translate_query)
        logger.debug(f"DDG News search: original='{query}' prepared='{search_query}'")

        results = []
        with DDGS() as ddgs:
            # Use news() instead of text() for recent news only
            for r in ddgs.news(search_query, max_results=max_results * 2):  # Fetch more to account for filtering
                url = r.get("url", r.get("link", ""))

                # Validate URL
                if not _is_valid_url(url):
                    logger.debug(f"Skipping invalid URL: {url}")
                    continue

                # Filter out excluded domains (Wikipedia, etc.)
                if _is_excluded_domain(url):
                    logger.debug(f"Skipping excluded domain: {url}")
                    continue

                domain = _extract_domain(url)
                doc = {
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("body", "")[:500],
                    "source": domain,
                    "source_name": f"DDGNews:{domain}",
                    "published": r.get("date", ""),  # DDG News provides date field
                }

                # 3-Layer date validation (published date → URL date → reject)
                if not _is_evidence_recent(doc, max_age_days=max_age_days):
                    continue

                results.append(doc)

                if len(results) >= max_results:
                    break

        logger.info(f"DuckDuckGo News: {len(results)} articles for '{query[:30]}...'")
        return results

    except Exception as e:
        error_type = SearchErrorType.API_ERROR
        if "timeout" in str(e).lower():
            error_type = SearchErrorType.TIMEOUT
        elif "rate" in str(e).lower() or "429" in str(e):
            error_type = SearchErrorType.RATE_LIMIT
        logger.error(f"DuckDuckGo News search error ({error_type.value}): {e}")
        get_search_stats("ddg_news").record_error(error_type, str(e))
        return []  # P2: Empty list but error is tracked


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
            for r in ddgs.text(query, max_results=max_results * 3):  # Fetch more to account for filtering
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

                domain = _extract_domain(url)
                doc = {
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("body", "")[:500],
                    "source": domain,
                    "source_name": f"DuckDuckGo:{domain}",
                    "published": "",  # DDG text search doesn't provide date
                }

                # 3-Layer date validation when filter_old is enabled
                # Note: DDG web search doesn't have published date, so this will
                # rely on URL patterns or reject (conservative approach)
                if filter_old and not _is_evidence_recent(doc, max_age_days=30):
                    continue

                results.append(doc)

                if len(results) >= max_results:
                    break

        logger.info(f"DuckDuckGo: {len(results)} results for '{query[:30]}...'")
        return results

    except Exception as e:
        error_type = SearchErrorType.API_ERROR
        if "timeout" in str(e).lower():
            error_type = SearchErrorType.TIMEOUT
        elif "rate" in str(e).lower() or "429" in str(e):
            error_type = SearchErrorType.RATE_LIMIT
        logger.error(f"DuckDuckGo search error ({error_type.value}): {e}")
        get_search_stats("ddg_web").record_error(error_type, str(e))
        return []  # P2: Empty list but error is tracked


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
                    "max_results": max_results * 2,  # Fetch more to account for filtering
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
                    logger.debug(f"Skipping invalid URL: {url}")
                    continue

                # Filter out excluded domains (Wikipedia, etc.)
                if _is_excluded_domain(url):
                    logger.debug(f"Skipping excluded domain: {url}")
                    continue

                domain = _extract_domain(url)
                doc = {
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("content", "")[:500],
                    "source": domain,
                    "source_name": f"Tavily:{domain}",
                    "score": r.get("score", 0),
                    "published": r.get("published_date", ""),  # Tavily may provide this
                }

                # 3-Layer date validation (published date → URL date → reject)
                if not _is_evidence_recent(doc, max_age_days=30):
                    continue

                results.append(doc)

                if len(results) >= max_results:
                    break

            logger.info(f"Tavily: {len(results)} results for '{query[:30]}...'")
            return results

    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return []  # Return empty list on error


# =============================================================================
# NEWS-SPECIFIC TOOLS (Use for breaking news and events)
# =============================================================================


@tool
async def search_news_gdelt(
    query: str,
    timespan: str = "24h",
    max_results: int = 20,
    translate_query: bool = True,
) -> list[dict]:
    """
    FREE global news search from GDELT. PRIMARY tool for news/events.

    ALWAYS use this FIRST for breaking news, conflicts, protests, disasters.
    Covers 100,000+ news sources worldwide in 100+ languages.

    P1 Enhancement: Automatically translates non-English queries for better results.

    Examples:
    - "Iran protest Tehran" -> Global coverage on Tehran protests
    - "Ukraine war Kharkiv" -> Coverage on Kharkiv war
    - "Syria airstrike" -> Coverage on Syria airstrikes

    Args:
        query: Search query (keywords, locations, topics)
        timespan: Search period (1h, 6h, 12h, 24h, 48h, 72h)
        max_results: Maximum number of results
        translate_query: Whether to translate non-English queries (default True)

    Returns:
        News list [{title, url, source, published, language, country}]
    """
    try:
        # P1: Translate query if needed
        search_query = await _prepare_search_query(query, translate=translate_query)
        logger.debug(f"GDELT search: original='{query}' prepared='{search_query}'")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params={
                    "query": search_query,  # P1: Use translated query
                    "mode": "artlist",
                    "maxrecords": str(max_results * 2),  # Fetch more to account for filtering
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

                # Filter out excluded domains (Wikipedia, etc.)
                if _is_excluded_domain(url):
                    logger.debug(f"Skipping excluded domain: {url}")
                    continue

                domain = _extract_domain(url)
                doc = {
                    "title": art.get("title", ""),
                    "url": url,
                    "source": domain,
                    "source_name": f"GDELT:{domain}",
                    "content": art.get("title", ""),  # GDELT은 content가 없어서 title 사용
                    "published": art.get("seendate", ""),  # GDELT seendate field
                    "language": art.get("language", ""),
                    "country": art.get("sourcecountry", ""),
                }

                # 3-Layer date validation (seendate → URL date → reject)
                if not _is_evidence_recent(doc, max_age_days=30):
                    continue

                results.append(doc)

                if len(results) >= max_results:
                    break

            logger.info(f"GDELT: {len(results)} articles for '{query[:30]}...'")
            return results

    except httpx.TimeoutException:
        logger.warning("GDELT request timed out")
        get_search_stats("gdelt").record_error(SearchErrorType.TIMEOUT, "Request timed out")
        return []  # P2: Empty list but error is tracked
    except Exception as e:
        error_type = SearchErrorType.API_ERROR
        if "rate" in str(e).lower() or "429" in str(e):
            error_type = SearchErrorType.RATE_LIMIT
        logger.error(f"GDELT search error ({error_type.value}): {e}")
        get_search_stats("gdelt").record_error(error_type, str(e))
        return []  # P2: Empty list but error is tracked


# =============================================================================
# P1: BRAVE SEARCH (Free tier: 2000 queries/month)
# =============================================================================


@tool
async def search_news_brave(
    query: str,
    max_results: int = 15,
    freshness: str = "pw",  # pd=day, pw=week, pm=month
    translate_query: bool = True,
) -> list[dict]:
    """
    FREE (limited) news search using Brave Search API.

    Brave Search provides high-quality results with a free tier of 2000 queries/month.
    Use this as a secondary source after GDELT for broader coverage.

    P1 Enhancement: Added as alternative search engine for better evidence coverage.

    Args:
        query: Search query (news topics, events)
        max_results: Maximum number of results (default 15)
        freshness: Time filter - pd (day), pw (week), pm (month)
        translate_query: Whether to translate non-English queries (default True)

    Returns:
        List of news results [{title, url, content, source, source_name, published}]
    """
    # Check if Brave API key is configured
    brave_api_key = getattr(agent_settings, 'brave_api_key', None)
    if not brave_api_key:
        logger.debug("Brave API key not configured, skipping")
        return []

    # Check cache
    cache_key = _get_cache_key("brave_news", query, max_results=max_results, freshness=freshness)
    cached = _get_cached_results(cache_key)
    if cached is not None:
        return cached

    try:
        # P1: Translate query if needed
        search_query = await _prepare_search_query(query, translate=translate_query)
        logger.debug(f"Brave News search: original='{query}' prepared='{search_query}'")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/news/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": brave_api_key,
                },
                params={
                    "q": search_query,
                    "count": max_results * 2,  # Fetch more to account for filtering
                    "freshness": freshness,
                },
            )

            if response.status_code == 429:
                logger.warning("Brave API rate limit reached")
                return []

            if response.status_code != 200:
                logger.warning(f"Brave API returned status {response.status_code}")
                return []

            data = response.json()
            results = []

            for item in data.get("results", []):
                url = item.get("url", "")

                # Validate URL
                if not _is_valid_url(url):
                    continue

                # Filter out excluded domains
                if _is_excluded_domain(url):
                    continue

                domain = _extract_domain(url)
                doc = {
                    "title": item.get("title", ""),
                    "url": url,
                    "content": item.get("description", "")[:500],
                    "source": domain,
                    "source_name": f"Brave:{domain}",
                    "published": item.get("age", ""),  # Brave provides relative age
                }

                # Date validation
                if not _is_evidence_recent(doc, max_age_days=30):
                    continue

                results.append(doc)

                if len(results) >= max_results:
                    break

            logger.info(f"Brave News: {len(results)} articles for '{query[:30]}...'")

            # Cache results
            _set_cached_results(cache_key, results)

            return results

    except httpx.TimeoutException:
        logger.warning("Brave Search request timed out")
        get_search_stats("brave").record_error(SearchErrorType.TIMEOUT, "Request timed out")
        return []  # P2: Empty list but error is tracked
    except Exception as e:
        error_type = SearchErrorType.API_ERROR
        if "rate" in str(e).lower() or "429" in str(e):
            error_type = SearchErrorType.RATE_LIMIT
        logger.error(f"Brave Search error ({error_type.value}): {e}")
        get_search_stats("brave").record_error(error_type, str(e))
        return []  # P2: Empty list but error is tracked


# =============================================================================
# P1: MULTI-ENGINE PARALLEL SEARCH
# =============================================================================


async def search_multi_engine(
    query: str,
    max_results_per_engine: int = 10,
    engines: list[str] | None = None,
    translate_query: bool = True,
) -> dict[str, list[dict]]:
    """
    P1: Parallel search across multiple engines for better evidence coverage.

    Searches GDELT, DuckDuckGo News, and Brave Search in parallel,
    returning results from all engines. This increases the chance of
    finding corroborating evidence for Gate 3.

    Args:
        query: Search query
        max_results_per_engine: Max results per engine (default 10)
        engines: List of engines to use. Options: "gdelt", "ddg", "brave"
                 Default: ["gdelt", "ddg", "brave"]
        translate_query: Whether to translate non-English queries

    Returns:
        Dict mapping engine name to results list
        {
            "gdelt": [{...}, ...],
            "ddg": [{...}, ...],
            "brave": [{...}, ...],
        }
    """
    if engines is None:
        engines = ["gdelt", "ddg", "brave"]

    # Create search tasks for each engine
    tasks = {}

    if "gdelt" in engines:
        tasks["gdelt"] = search_news_gdelt.ainvoke({
            "query": query,
            "max_results": max_results_per_engine,
            "translate_query": translate_query,
        })

    if "ddg" in engines:
        tasks["ddg"] = search_news_ddg.ainvoke({
            "query": query,
            "max_results": max_results_per_engine,
            "translate_query": translate_query,
        })

    if "brave" in engines:
        # Only include if API key is configured
        if getattr(agent_settings, 'brave_api_key', None):
            tasks["brave"] = search_news_brave.ainvoke({
                "query": query,
                "max_results": max_results_per_engine,
                "translate_query": translate_query,
            })

    if not tasks:
        logger.warning("No search engines available")
        return {}

    # Run searches in parallel
    engine_names = list(tasks.keys())
    results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)

    # Collect results
    results = {}
    total_count = 0

    for engine_name, engine_results in zip(engine_names, results_list):
        if isinstance(engine_results, Exception):
            logger.error(f"{engine_name} search failed: {engine_results}")
            results[engine_name] = []
        else:
            results[engine_name] = engine_results or []
            total_count += len(results[engine_name])

    logger.info(
        f"Multi-engine search complete: {total_count} total results "
        f"(gdelt={len(results.get('gdelt', []))}, "
        f"ddg={len(results.get('ddg', []))}, "
        f"brave={len(results.get('brave', []))})"
    )

    return results


async def search_evidence(
    query: str,
    min_results: int = 3,
    max_results: int = 15,
    translate_query: bool = True,
) -> list[dict]:
    """
    P1: Smart evidence search with fallback strategy.

    Searches multiple engines in parallel and deduplicates results.
    If initial search doesn't find enough results, expands to paid sources.

    Args:
        query: Search query for evidence
        min_results: Minimum results needed (triggers fallback if not met)
        max_results: Maximum total results to return
        translate_query: Whether to translate non-English queries

    Returns:
        Deduplicated list of evidence documents
    """
    # Check cache first
    cache_key = _get_cache_key("evidence", query, min_results=min_results, max_results=max_results)
    cached = _get_cached_results(cache_key)
    if cached is not None:
        return cached

    # Phase 1: Free multi-engine search
    multi_results = await search_multi_engine(
        query=query,
        max_results_per_engine=10,
        engines=["gdelt", "ddg", "brave"],
        translate_query=translate_query,
    )

    # Deduplicate results by URL
    seen_urls: set[str] = set()
    all_results: list[dict] = []

    for engine_name, engine_results in multi_results.items():
        for doc in engine_results:
            url = doc.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                doc["search_engine"] = engine_name
                all_results.append(doc)

    logger.info(f"Phase 1 (free engines): {len(all_results)} unique results for '{query[:30]}...'")

    # Phase 2: If not enough results, try Tavily (paid)
    if len(all_results) < min_results and agent_settings.tavily_api_key:
        logger.info(f"Phase 2: Not enough results ({len(all_results)} < {min_results}), trying Tavily")

        tavily_results = await search_web.ainvoke({
            "query": query,
            "max_results": max_results - len(all_results),
        })

        for doc in tavily_results or []:
            url = doc.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                doc["search_engine"] = "tavily"
                all_results.append(doc)

        logger.info(f"Phase 2 complete: {len(all_results)} total results")

    # Limit to max_results
    final_results = all_results[:max_results]

    # Cache results
    _set_cached_results(cache_key, final_results)

    return final_results
