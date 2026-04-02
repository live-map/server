"""
Async Tavily API wrapper for web search.

Tavily는 AI 에이전트를 위한 검색 API로,
관련성 높은 웹 검색 결과를 반환합니다.

v3: topic="news" 제거 (한국어→영문뉴스 매칭 근본 원인),
    한국어 도메인 스티어링, 비한국어 결과 필터.
"""

import logging
import re

from tavily import AsyncTavilyClient

from app.services.research.config import (
    ACADEMIC_DOMAINS,
    CREDIBILITY_HIGH_THRESHOLD,
    CREDIBILITY_MEDIUM_THRESHOLD,
    GOV_DOMAINS,
    KOREAN_TRUSTED_DOMAINS,
    NEWS_DOMAINS,
    TAVILY_CONTENT_MAX,
    TAVILY_EXCLUDE_DOMAINS,
    TAVILY_RAW_CONTENT_MAX,
    ai_settings,
)
from app.services.research.state import SourceItem

logger = logging.getLogger(__name__)

_KOREAN_RE = re.compile(r"[가-힣]")


def _is_korean_query(query: str) -> bool:
    """쿼리에 한글이 포함되어 있는지 확인합니다."""
    return bool(_KOREAN_RE.search(query))


def _has_korean_chars(text: str) -> bool:
    """텍스트에 한글 문자가 하나라도 있는지 확인합니다."""
    return bool(_KOREAN_RE.search(text))


def _classify_source_type(url: str) -> str:
    """URL 도메인을 기반으로 source_type을 분류합니다."""
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


class TavilyClient:
    """Tavily 웹 검색 래퍼."""

    def __init__(self) -> None:
        self.client = AsyncTavilyClient(api_key=ai_settings.TAVILY_API_KEY)

    async def search(
        self,
        query: str,
        max_results: int = 7,
        include_answer: bool = False,
    ) -> list[SourceItem]:
        """웹 검색을 수행하고 SourceItem 목록을 반환합니다."""
        is_korean = _is_korean_query(query)

        try:
            search_kwargs: dict = {
                "query": query,
                "max_results": max_results,
                "include_answer": include_answer,
                "search_depth": "advanced",
                "exclude_domains": TAVILY_EXCLUDE_DOMAINS,
                "include_raw_content": True,
            }

            # 한국어 쿼리: 한국 신뢰 도메인 스티어링
            # include_domains와 exclude_domains를 동시 사용하면 충돌 —
            # include가 설정되면 exclude 제거 (include가 우선)
            if is_korean:
                search_kwargs["include_domains"] = KOREAN_TRUSTED_DOMAINS
                del search_kwargs["exclude_domains"]

            response = await self.client.search(**search_kwargs)

            sources: list[SourceItem] = []
            for result in response.get("results", []):
                title = result.get("title", "")

                # 한국어 쿼리인데 제목에 한글이 없으면 제외
                if is_korean and not _has_korean_chars(title):
                    logger.debug("Filtered non-Korean result: %s", title[:60])
                    continue

                score = result.get("score", 0)
                if score > CREDIBILITY_HIGH_THRESHOLD:
                    credibility = "HIGH"
                elif score > CREDIBILITY_MEDIUM_THRESHOLD:
                    credibility = "MEDIUM"
                else:
                    credibility = "LOW"

                # raw_content가 있으면 2000자까지, 없으면 content 800자
                raw = result.get("raw_content") or ""
                content = result.get("content", "")
                if raw and len(raw) > len(content):
                    snippet = raw[:TAVILY_RAW_CONTENT_MAX]
                else:
                    snippet = content[:TAVILY_CONTENT_MAX]

                url = result.get("url", "")
                source_type = _classify_source_type(url)

                sources.append(
                    SourceItem(
                        title=title,
                        url=url,
                        source_type=source_type,
                        description=title,
                        content_snippet=snippet,
                        credibility=credibility,
                    )
                )

            logger.info("Tavily search '%s': %d results (korean=%s)", query[:50], len(sources), is_korean)
            return sources

        except Exception as e:
            logger.error("Tavily search failed for '%s': %s", query[:50], e)
            return []
