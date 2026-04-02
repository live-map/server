"""
자동 썸네일 클라이언트.

LLM으로 한국어 제목 → 영문 키워드 추출 후 Unsplash에서 이미지 검색.
Unsplash 결과 없으면 카테고리 기반 fallback 키워드로 재시도.
"""

import logging

import httpx

from app.services.research.config import UNSPLASH_TIMEOUT, ai_settings

logger = logging.getLogger(__name__)

_UNSPLASH_API = "https://api.unsplash.com/search/photos"

# 카테고리 → Unsplash 검색에 적합한 fallback 키워드
_CATEGORY_KEYWORDS: dict[str, str] = {
    "정치": "government parliament",
    "경제": "economy finance city",
    "사회": "people community city",
    "기술": "technology digital",
    "환경": "nature environment green",
    "문화": "culture art festival",
    "스포츠": "sports stadium",
    "교육": "education university library",
    "기타": "abstract minimal",
}


async def _extract_keywords(title: str) -> str:
    """LLM으로 한국어 poll 제목에서 Unsplash 검색용 영문 키워드를 추출합니다."""
    llm = ai_settings.get_chat_model(role="planner", max_tokens=50, temperature=0.0)
    prompt = (
        "You are helping find a stock photo for a poll. "
        "Extract 2-3 broad, visual English keywords suitable for Unsplash photo search. "
        "Prefer concrete, photographic subjects over abstract concepts.\n"
        "Examples:\n"
        "- '대학 등록금 동결' → 'university students campus'\n"
        "- '핵발전소 확대' → 'nuclear power plant energy'\n"
        "- '재택근무 생산성' → 'remote work laptop home'\n\n"
        f"Title: {title}\n"
        "Keywords:"
    )
    try:
        response = await llm.ainvoke(prompt)
        keywords = response.content.strip().strip('"').strip("'")
        logger.info("[Thumbnail] Extracted keywords: '%s' from title: '%s'", keywords, title[:50])
        return keywords
    except Exception as e:
        logger.error("[Thumbnail] Keyword extraction failed: %s", e)
        return ""


async def _search_unsplash(keywords: str) -> str | None:
    """Unsplash API로 이미지 검색."""
    access_key = ai_settings.UNSPLASH_ACCESS_KEY
    if not access_key or not keywords:
        return None

    try:
        async with httpx.AsyncClient(timeout=UNSPLASH_TIMEOUT) as client:
            response = await client.get(
                _UNSPLASH_API,
                params={
                    "query": keywords,
                    "orientation": "landscape",
                    "per_page": 1,
                },
                headers={"Authorization": f"Client-ID {access_key}"},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                url = results[0]["urls"]["regular"]
                logger.info("[Thumbnail] Unsplash found: %s", url[:80])
                return url
    except Exception as e:
        logger.warning("[Thumbnail] Unsplash search failed for '%s': %s", keywords[:30], e)
    return None


async def fetch_thumbnail(title: str, category: str | None = None) -> str | None:
    """
    Poll 제목/카테고리로 Unsplash 썸네일을 검색합니다.

    1차: LLM 키워드 추출 → Unsplash 검색
    2차: 카테고리 fallback 키워드 → Unsplash 검색
    """
    # 1차: LLM 키워드
    keywords = await _extract_keywords(title)
    if keywords:
        url = await _search_unsplash(keywords)
        if url:
            return url
        logger.info("[Thumbnail] No results for LLM keywords '%s', trying category fallback", keywords[:30])

    # 2차: 카테고리 fallback
    fallback = _CATEGORY_KEYWORDS.get(category or "", _CATEGORY_KEYWORDS["기타"])
    url = await _search_unsplash(fallback)
    if url:
        return url

    logger.warning("[Thumbnail] No thumbnail found for '%s'", title[:30])
    return None
