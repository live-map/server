"""
DuckDuckGo 검색 클라이언트 — Tavily fallback용.

API 키 불필요, 무료 검색. DDGS.text()를 asyncio.to_thread로 래핑.
TavilyClient과 동일한 list[SourceItem] 인터페이스.
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

from duckduckgo_search import DDGS

from app.services.research.config import (
    ACADEMIC_DOMAINS,
    BLOCKED_DOMAINS,
    GOV_DOMAINS,
    MAX_SNIPPET_LENGTH,
    NEWS_DOMAINS,
)
from app.services.research.state import SourceItem

logger = logging.getLogger(__name__)

_KOREAN_RE = re.compile(r"[가-힣]")


def _classify_source_type(url: str) -> str:
    url_lower = url.lower()
    for domain in NEWS_DOMAINS:
        if domain in url_lower:
            return "NEWS"
    for domain in GOV_DOMAINS:
        if domain in url_lower:
            return "ARTICLE"
    for domain in ACADEMIC_DOMAINS:
        if domain in url_lower:
            return "PAPER"
    return "OTHER"


def _is_blocked(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return True
    return any(domain in netloc for domain in BLOCKED_DOMAINS)


class DuckDuckGoClient:
    """DuckDuckGo 웹 검색 래퍼 — Tavily fallback용."""

    async def search(
        self,
        query: str,
        max_results: int = 7,
    ) -> list[SourceItem]:
        """웹 검색을 수행하고 SourceItem 목록을 반환합니다."""
        is_korean = bool(_KOREAN_RE.search(query))
        region = "kr-kr" if is_korean else "wt-wt"

        try:
            def _sync_search():
                with DDGS() as ddgs:
                    return ddgs.text(query, region=region, max_results=max_results)

            raw_results = await asyncio.to_thread(_sync_search)

            sources: list[SourceItem] = []
            for result in raw_results:
                url = result.get("href", "")
                if not url or _is_blocked(url):
                    continue

                title = result.get("title", "")
                body = result.get("body", "")

                sources.append(
                    SourceItem(
                        title=title,
                        url=url,
                        source_type=_classify_source_type(url),
                        description=title,
                        content_snippet=body[:MAX_SNIPPET_LENGTH],
                        credibility="MEDIUM",  # DuckDuckGo는 score 없으므로 MEDIUM 기본값
                    )
                )

            logger.info(
                "DuckDuckGo search '%s': %d results (korean=%s)",
                query[:50], len(sources), is_korean,
            )
            return sources

        except Exception as e:
            logger.error("DuckDuckGo search failed for '%s': %s", query[:50], e)
            return []
