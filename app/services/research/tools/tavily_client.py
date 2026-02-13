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

from app.services.research.config import ai_settings
from app.services.research.state import SourceItem

logger = logging.getLogger(__name__)

# API 수준에서 차단할 도메인 (검색 결과 자체에서 제외)
_EXCLUDE_DOMAINS = [
    "namu.wiki",
    "wikipedia.org",
    "ko.wikipedia.org",
    "en.wikipedia.org",
    "blog.naver.com",
    "m.blog.naver.com",
    "tistory.com",
    "brunch.co.kr",
    "medium.com",
    "velog.io",
    "reddit.com",
    "youtube.com",
    "quora.com",
    "dcinside.com",
    "fmkorea.com",
    "theqoo.net",
    "clien.net",
    "ruliweb.com",
    "ppomppu.co.kr",
    "notion.so",
]

# 한국어 쿼리일 때 우선 포함할 신뢰 도메인
_KOREAN_TRUSTED_DOMAINS = [
    "bbc.com/korean",
    "yonhapnews.co.kr",
    "hani.co.kr",
    "khan.co.kr",
    "chosun.com",
    "donga.com",
    "joongang.co.kr",
    "mk.co.kr",
    "mt.co.kr",
    "hankyung.com",
    "sedaily.com",
    "yna.co.kr",
    "kbs.co.kr",
    "sbs.co.kr",
    "mbc.co.kr",
    "bok.or.kr",
    "kostat.go.kr",
    "kdi.re.kr",
    "nars.go.kr",
]

_KOREAN_RE = re.compile(r"[가-힣]")


def _is_korean_query(query: str) -> bool:
    """쿼리에 한글이 포함되어 있는지 확인합니다."""
    return bool(_KOREAN_RE.search(query))


def _has_korean_chars(text: str) -> bool:
    """텍스트에 한글 문자가 하나라도 있는지 확인합니다."""
    return bool(_KOREAN_RE.search(text))


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
                "exclude_domains": _EXCLUDE_DOMAINS,
                "include_raw_content": True,
            }

            # 한국어 쿼리: 한국 신뢰 도메인 스티어링
            if is_korean:
                search_kwargs["include_domains"] = _KOREAN_TRUSTED_DOMAINS

            response = await self.client.search(**search_kwargs)

            sources: list[SourceItem] = []
            for result in response.get("results", []):
                title = result.get("title", "")

                # 한국어 쿼리인데 제목에 한글이 없으면 제외
                if is_korean and not _has_korean_chars(title):
                    logger.debug(f"Filtered non-Korean result: {title[:60]}")
                    continue

                score = result.get("score", 0)
                if score > 0.7:
                    credibility = "HIGH"
                elif score > 0.4:
                    credibility = "MEDIUM"
                else:
                    credibility = "LOW"

                # raw_content가 있으면 2000자까지, 없으면 content 800자
                raw = result.get("raw_content") or ""
                content = result.get("content", "")
                if raw and len(raw) > len(content):
                    snippet = raw[:2000]
                else:
                    snippet = content[:800]

                sources.append(
                    SourceItem(
                        title=title,
                        url=result.get("url", ""),
                        source_type="NEWS",
                        description=title,
                        content_snippet=snippet,
                        credibility=credibility,
                    )
                )

            logger.info(f"Tavily search '{query[:50]}': {len(sources)} results (korean={is_korean})")
            return sources

        except Exception as e:
            logger.error(f"Tavily search failed for '{query[:50]}': {e}")
            return []
