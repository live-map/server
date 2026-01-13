"""
Search tools for investigation agent.

- search_web: Tavily-based web search
- search_news_gdelt: GDELT news search (free)
"""

import logging

import httpx
from langchain_core.tools import tool

from app.agent.config import agent_settings

logger = logging.getLogger(__name__)


@tool
async def search_web(query: str, max_results: int = 10) -> list[dict]:
    """
    Search news, articles, and information from the web.

    This tool allows the agent to search freely with any search query.
    Examples:
    - "Iran International Iran protest" -> Iran-focused media articles on protests
    - "Tehran protest latest" -> Latest Tehran protest news
    - "BBC Persian Iran" -> BBC Persian Iran coverage
    - "Ukraine war Kyiv Independent" -> Ukraine-focused media coverage

    The agent can include source names in the query to find specific sources.

    Args:
        query: Search query (freely combine source names, keywords, regions)
        max_results: Maximum number of results (default 10)

    Returns:
        List of results [{title, url, content, source}]
    """
    if not agent_settings.tavily_api_key:
        return [{"error": "Tavily API key not configured", "results": []}]

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
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],
                    "source": r.get("url", "").split("/")[2] if r.get("url") else "",
                    "score": r.get("score", 0),
                })

            return results

    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return [{"error": str(e), "results": []}]


@tool
async def search_news_gdelt(query: str, timespan: str = "24h", max_results: int = 20) -> list[dict]:
    """
    Search global news from GDELT. (Free, 100,000+ sources)

    Searches worldwide news with keywords only, without specifying sources.
    The agent can narrow scope by including source names or regions in the query.

    Examples:
    - "Iran protest Tehran" -> Global coverage on Tehran protests
    - "Ukraine war Kharkiv" -> Coverage on Kharkiv war
    - "Syria airstrike" -> Coverage on Syria airstrikes

    Args:
        query: Search query
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
            response.raise_for_status()
            data = response.json()

            results = []
            for art in data.get("articles", []):
                results.append({
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "source": art.get("domain", ""),
                    "published": art.get("seendate", ""),
                    "language": art.get("language", ""),
                    "country": art.get("sourcecountry", ""),
                })

            return results

    except Exception as e:
        logger.error(f"GDELT search error: {e}")
        return [{"error": str(e), "results": []}]
