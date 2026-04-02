"""
Web Search node — Tavily API로 웹 검색을 수행합니다.

v2: Jina Reader로 content_snippet 보강, Tavily exclude_domains로
    API 수준 차단 (post-filtering은 2차 안전장치).
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

from app.services.research.config import (
    BLOCKED_DOMAINS,
    BLOCKED_URL_PATTERNS,
    DUCKDUCKGO_DELAY,
    DUCKDUCKGO_MAX_RESULTS,
    JINA_ENRICH_LIMIT,
    JINA_ENRICH_THRESHOLD,
    JINA_MAX_CHARS,
    MAX_SNIPPET_LENGTH,
    MIN_SNIPPET_LENGTH,
    TAVILY_MAX_RESULTS,
    TRUSTED_DOMAINS,
    ai_settings,
)
from app.services.research.state import ResearchState, SourceItem
from app.services.research.tools.duckduckgo_client import DuckDuckGoClient
from app.services.research.tools.jina_reader import JinaReader
from app.services.research.tools.tavily_client import TavilyClient

logger = logging.getLogger(__name__)


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_trusted_domain(url: str) -> bool:
    domain = _get_domain(url)
    return any(trusted in domain for trusted in TRUSTED_DOMAINS)


def _is_relevant_source(source: SourceItem) -> bool:
    url = source.get("url", "")
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            return False
    if BLOCKED_URL_PATTERNS.search(url):
        return False
    snippet = source.get("content_snippet", "")
    if len(snippet) < MIN_SNIPPET_LENGTH:
        return False
    return True


def _boost_trusted_credibility(source: SourceItem) -> SourceItem:
    if _is_trusted_domain(source.get("url", "")):
        return SourceItem(
            title=source["title"],
            url=source["url"],
            source_type=source["source_type"],
            description=source["description"],
            content_snippet=source["content_snippet"],
            credibility="HIGH",
        )
    return source


async def _enrich_with_jina(sources: list[SourceItem]) -> list[SourceItem]:
    """content_snippet이 짧은 출처를 Jina Reader로 병렬 보강합니다."""
    reader = JinaReader()
    sem = asyncio.Semaphore(5)

    async def _enrich_one(source: SourceItem) -> SourceItem:
        async with sem:
            snippet = source.get("content_snippet", "")
            if len(snippet) < JINA_ENRICH_THRESHOLD:
                content = await reader.extract(source["url"], max_chars=JINA_MAX_CHARS)
                if content and len(content) > len(snippet):
                    enriched = SourceItem(
                        title=source["title"],
                        url=source["url"],
                        source_type=source["source_type"],
                        description=source["description"],
                        content_snippet=content[:MAX_SNIPPET_LENGTH],
                        credibility=source["credibility"],
                    )
                    logger.debug("[WebSearch] Enriched via Jina: %s", source["title"][:40])
                    return enriched
            return source

    return await asyncio.gather(*[_enrich_one(s) for s in sources])


async def _search_with_tavily(queries: list[str]) -> list[SourceItem]:
    """Tavily로 검색합니다. 실패 시 빈 리스트 반환."""
    if not ai_settings.TAVILY_API_KEY:
        logger.info("[WebSearch] No Tavily API key, skipping Tavily search")
        return []

    client = TavilyClient()
    tasks = [client.search(q, max_results=TAVILY_MAX_RESULTS) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    sources: list[SourceItem] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("[WebSearch] Tavily query failed: %s", result)
            continue
        sources.extend(result)
    return sources


async def _search_with_duckduckgo(queries: list[str]) -> list[SourceItem]:
    """DuckDuckGo fallback 검색."""
    logger.info("[WebSearch] Falling back to DuckDuckGo for %d queries", len(queries))
    client = DuckDuckGoClient()
    sources: list[SourceItem] = []
    # DuckDuckGo는 rate limit 방지를 위해 순차 실행 + 짧은 딜레이
    for query in queries:
        result = await client.search(query, max_results=DUCKDUCKGO_MAX_RESULTS)
        sources.extend(result)
        if len(queries) > 1:
            await asyncio.sleep(DUCKDUCKGO_DELAY)
    return sources


async def web_search_node(state: ResearchState) -> dict:
    """모든 웹 검색 쿼리를 병렬로 실행합니다. Tavily 실패 시 DuckDuckGo fallback."""
    queries = state.get("search_queries", [])
    if not queries:
        logger.warning("[WebSearch] No search queries provided")
        return {"web_sources": []}

    logger.info("[WebSearch] Searching %d queries", len(queries))

    # 1차: Tavily 검색
    raw_sources = await _search_with_tavily(queries)

    # 2차: Tavily 결과가 없으면 DuckDuckGo fallback
    if not raw_sources:
        raw_sources = await _search_with_duckduckgo(queries)

    all_sources: list[SourceItem] = []
    seen_urls: set[str] = set()
    filtered_count = 0

    for source in raw_sources:
        if source["url"] in seen_urls:
            continue
        seen_urls.add(source["url"])
        if _is_relevant_source(source):
            all_sources.append(_boost_trusted_credibility(source))
        else:
            filtered_count += 1

    if filtered_count:
        logger.info("[WebSearch] Filtered out %d irrelevant sources", filtered_count)

    # Jina Reader로 짧은 snippet 보강 (상위 결과만, 나머지 보존)
    if all_sources:
        short_count = sum(1 for s in all_sources if len(s.get("content_snippet", "")) < JINA_ENRICH_THRESHOLD)
        if short_count > 0:
            logger.info("[WebSearch] Enriching %d sources with short snippets via Jina", short_count)
            enriched = await _enrich_with_jina(all_sources[:JINA_ENRICH_LIMIT])
            all_sources = enriched + all_sources[JINA_ENRICH_LIMIT:]

    # 신뢰 도메인 출처를 상위로 정렬
    all_sources.sort(
        key=lambda s: (0 if s["credibility"] == "HIGH" else 1, s["title"])
    )

    logger.info("[WebSearch] Collected %d unique relevant sources", len(all_sources))
    return {"web_sources": all_sources}
