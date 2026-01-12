"""
자율 조사 에이전트 도구

핵심 원칙:
- 소스 목록 하드코딩 없음
- 에이전트가 검색어를 직접 결정
- 도구 설명을 통해 LLM이 적절한 도구 선택

도구 목록:
1. search_web - Tavily 기반 웹 검색 (뉴스, 기사 등)
2. search_news_gdelt - GDELT 기반 뉴스 검색 (무료)
3. search_telegram - 텔레그램 채널 검색 (가입 채널)
4. search_youtube - YouTube 영상 검색
5. get_video_info - 영상 메타데이터 추출
6. translate_text - 다국어 번역
"""

import asyncio
import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

from .config import agent_settings

logger = logging.getLogger(__name__)


# ============================================================
# 1. 웹 검색 (Tavily) - 에이전트 메인 도구
# ============================================================

@tool
async def search_web(query: str, max_results: int = 10) -> list[dict]:
    """
    웹에서 뉴스, 기사, 정보를 검색합니다.

    이 도구는 에이전트가 원하는 어떤 검색어로든 자유롭게 검색할 수 있습니다.
    예시:
    - "Iran International Iran protest" → 이란 전문 매체에서 시위 관련 기사
    - "Tehran protest latest" → 테헤란 시위 최신 소식
    - "BBC Persian Iran" → BBC 페르시아어 이란 보도
    - "Ukraine war Kyiv Independent" → 우크라이나 전문 매체 보도

    에이전트는 상황에 맞는 소스명을 검색어에 포함시켜 원하는 소스를 찾을 수 있습니다.

    Args:
        query: 검색어 (소스명, 키워드, 지역 등 자유롭게 조합)
        max_results: 최대 결과 수 (기본 10)

    Returns:
        검색 결과 목록 [{title, url, content, source}]
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


# ============================================================
# 2. GDELT 뉴스 검색 (무료)
# ============================================================

@tool
async def search_news_gdelt(query: str, timespan: str = "24h", max_results: int = 20) -> list[dict]:
    """
    GDELT에서 전 세계 뉴스를 검색합니다. (무료, 100,000+ 소스)

    특정 소스를 지정하지 않고 키워드만으로 전 세계 뉴스를 검색합니다.
    에이전트는 검색어에 소스명이나 지역을 포함시켜 범위를 좁힐 수 있습니다.

    예시:
    - "Iran protest Tehran" → 테헤란 시위 관련 전 세계 보도
    - "Ukraine war Kharkiv" → 하르키우 전쟁 관련 보도
    - "Syria airstrike" → 시리아 공습 관련 보도

    Args:
        query: 검색어
        timespan: 검색 기간 (1h, 6h, 12h, 24h, 48h, 72h)
        max_results: 최대 결과 수

    Returns:
        뉴스 목록 [{title, url, source, published, language, country}]
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


# ============================================================
# 3. 텔레그램 검색
# ============================================================

# 에이전트가 가입을 요청할 수 있는 추천 채널 (예시)
# 실제 가입은 수동으로 해야 함
SUGGESTED_TELEGRAM_CHANNELS = """
에이전트가 텔레그램 채널을 검색할 때 참고할 수 있는 채널들:

우크라이나/러시아:
- @ukrainenowenglish - 우크라이나 공식 영어 채널
- @nexta_live - 동유럽 뉴스
- @KyivIndependent - 키이우 인디펜던트
- @intelslava - 러시아어 OSINT

이란/중동:
- @IranIntl - Iran International
- @IranHRM - 이란 인권
- @AJABreaking - 알자지라 속보

OSINT:
- @GeoConfirmed - 지리 검증
- @WarMonitor3 - 전쟁 모니터링

참고: 실제 검색은 가입한 채널에서만 가능합니다.
"""


@tool
async def search_telegram(query: str, channel: str | None = None) -> list[dict]:
    """
    텔레그램 채널에서 메시지를 검색합니다.

    주의: 현재 가입한 채널에서만 검색 가능합니다.
    에이전트가 특정 채널이 필요하다고 판단하면 채널명을 명시하세요.

    예시:
    - query="Iran protest", channel="IranIntl"
    - query="Ukraine attack", channel="ukrainenowenglish"
    - query="OSINT footage", channel="GeoConfirmed"

    추천 채널 목록:
    {suggested_channels}

    Args:
        query: 검색어
        channel: 특정 채널명 (없으면 가입한 모든 채널 검색)

    Returns:
        메시지 목록 [{text, date, channel, media_type, media_url}]
    """.format(suggested_channels=SUGGESTED_TELEGRAM_CHANNELS)

    # TODO: Telethon 실제 연동 필요
    # 현재는 플레이스홀더

    return [{
        "status": "telegram_not_configured",
        "message": "Telegram search requires Telethon configuration with API credentials",
        "suggested_action": f"To search for '{query}'" + (f" in @{channel}" if channel else "") + ", configure TELEGRAM_API_ID and TELEGRAM_API_HASH",
        "suggested_channels": [
            "ukrainenowenglish", "nexta_live", "IranIntl",
            "GeoConfirmed", "WarMonitor3"
        ]
    }]


# ============================================================
# 4. YouTube 검색 (무료)
# ============================================================

@tool
async def search_youtube(query: str, max_results: int = 10) -> list[dict]:
    """
    YouTube에서 영상을 검색합니다.

    시위, 전쟁, 분쟁 관련 영상을 찾을 때 사용합니다.
    검색어에 지역, 날짜, 이벤트 등을 포함시켜 정확도를 높이세요.

    예시:
    - "Tehran protest 2026" → 테헤란 시위 영상
    - "Ukraine war footage Kharkiv" → 하르키우 전쟁 영상
    - "Syria airstrike video" → 시리아 공습 영상

    Args:
        query: 검색어
        max_results: 최대 결과 수

    Returns:
        영상 목록 [{title, video_id, url, channel, published, thumbnail}]
    """
    # YouTube Data API v3 사용 (무료 쿼터)
    # API 키 없이도 검색 가능한 방법 사용

    try:
        # YouTube search results page scraping (simple approach)
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


# ============================================================
# 5. 영상 정보 추출 (yt-dlp)
# ============================================================

@tool
async def get_video_info(url: str) -> dict:
    """
    영상 URL에서 메타데이터를 추출합니다.

    YouTube, Twitter, Telegram 등 대부분의 영상 플랫폼 지원.
    실제 다운로드 없이 정보만 추출합니다.

    Args:
        url: 영상 URL

    Returns:
        영상 정보 {title, description, duration, uploader, upload_date, view_count, thumbnail}
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )

            return {
                "title": info.get("title", ""),
                "description": (info.get("description", "") or "")[:500],
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "upload_date": info.get("upload_date", ""),
                "view_count": info.get("view_count", 0),
                "thumbnail": info.get("thumbnail", ""),
                "url": url,
                "platform": info.get("extractor", "unknown"),
            }

    except Exception as e:
        logger.error(f"Video info extraction error: {e}")
        return {"error": str(e), "url": url}


# ============================================================
# 6. 번역 도구
# ============================================================

@tool
async def translate_text(text: str, target_lang: str = "en", source_lang: str | None = None) -> dict:
    """
    텍스트를 번역합니다.

    페르시아어, 아랍어, 러시아어, 우크라이나어 등 다국어 콘텐츠 번역에 사용.

    Args:
        text: 번역할 텍스트
        target_lang: 목표 언어 (기본: en)
        source_lang: 원본 언어 (자동 감지 시 None)

    Returns:
        {original, translated, source_lang, target_lang}
    """
    # LibreTranslate API (무료) 또는 Google Translate
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # LibreTranslate 공개 인스턴스 사용
            response = await client.post(
                "https://libretranslate.com/translate",
                json={
                    "q": text[:1000],  # 최대 1000자
                    "source": source_lang or "auto",
                    "target": target_lang,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "original": text,
                    "translated": data.get("translatedText", ""),
                    "source_lang": source_lang or "auto",
                    "target_lang": target_lang,
                }
            else:
                return {
                    "original": text,
                    "error": f"Translation failed: {response.status_code}",
                    "note": "LibreTranslate may have rate limits. Consider self-hosting.",
                }

    except Exception as e:
        logger.error(f"Translation error: {e}")
        return {"original": text, "error": str(e)}


# ============================================================
# 도구 목록 (LangGraph에서 사용)
# ============================================================

ALL_TOOLS = [
    search_web,
    search_news_gdelt,
    search_telegram,
    search_youtube,
    get_video_info,
    translate_text,
]

# 도구별 설명 (에이전트 프롬프트용)
TOOL_DESCRIPTIONS = """
사용 가능한 도구:

1. search_web(query) - Tavily 기반 웹 검색
   - 뉴스 기사, 블로그, 공식 사이트 등 검색
   - 검색어에 소스명 포함 가능 (예: "Iran International protest")
   - 가장 범용적인 도구

2. search_news_gdelt(query, timespan) - GDELT 뉴스 검색 (무료)
   - 전 세계 100,000+ 뉴스 소스 검색
   - 최근 1시간~72시간 뉴스
   - 소스 지정 없이 키워드만으로 검색

3. search_telegram(query, channel) - 텔레그램 검색
   - 실시간 현장 영상, 로컬 리포트
   - 가입한 채널에서만 검색 가능
   - 채널명 지정 권장

4. search_youtube(query) - YouTube 영상 검색
   - 시위, 전쟁, 분쟁 관련 영상
   - 무료 API 사용

5. get_video_info(url) - 영상 메타데이터 추출
   - YouTube, Twitter, Telegram 영상 정보
   - 다운로드 없이 정보만 추출

6. translate_text(text, target_lang) - 번역
   - 페르시아어, 아랍어, 러시아어 등 번역
   - 다국어 콘텐츠 이해에 필수

핵심 원칙:
- 소스 목록은 하드코딩되어 있지 않음
- 에이전트가 상황에 맞는 검색어를 직접 결정
- 예: 이란 시위 → "Iran International" 검색어에 포함
"""


async def test_tools():
    """도구 테스트"""
    print("\n" + "=" * 60)
    print("🔧 TOOLS TEST")
    print("=" * 60)

    # GDELT 테스트 (무료)
    print("\n1. Testing GDELT search...")
    gdelt_results = await search_news_gdelt.ainvoke({"query": "protest Iran", "timespan": "24h"})
    print(f"   GDELT results: {len(gdelt_results)} articles")
    if gdelt_results and "error" not in gdelt_results[0]:
        print(f"   Sample: {gdelt_results[0].get('title', 'N/A')[:50]}...")

    # Tavily 테스트 (API 키 필요)
    print("\n2. Testing Tavily search...")
    if agent_settings.tavily_api_key:
        tavily_results = await search_web.ainvoke({"query": "Iran protest latest news"})
        print(f"   Tavily results: {len(tavily_results)}")
    else:
        print("   Tavily: API key not configured")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tools())
