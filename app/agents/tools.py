"""
에이전트 도구들 - 에이전트가 자율적으로 선택하여 사용

도구 설명이 중요함: 에이전트가 언제 어떤 도구를 쓸지 판단하는 근거
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import feedparser
import httpx
from langchain_core.tools import tool

from .config import agent_settings

logger = logging.getLogger(__name__)

# ============================================================
# 웹 검색 도구 (Tavily)
# ============================================================


@tool
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    웹에서 뉴스/정보를 검색합니다. 전쟁, 시위, 테러 등 국제 정세 관련 정보 검색에 사용하세요.

    Args:
        query: 검색어 (영어 권장, 예: "Iran protest", "Ukraine war", "Gaza conflict")
        max_results: 최대 결과 수 (기본 5개, 비용 절약)

    Returns:
        검색 결과 목록 (제목, 내용, URL, 발행일)
    """
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=agent_settings.tavily_api_key)
        response = client.search(
            query=query,
            search_depth="basic",  # 비용 절약 (advanced는 2배 비용)
            max_results=max_results,
            include_answer=False,  # 비용 절약
        )

        results = []
        for item in response.get("results", []):
            results.append(
                {
                    "source_type": "news",
                    "source_name": item.get("url", "").split("/")[2]
                    if item.get("url")
                    else "unknown",
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("published_date"),
                }
            )
        return results

    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return []


# ============================================================
# RSS 피드 도구
# ============================================================

# 주요 뉴스 RSS 피드
RSS_FEEDS = {
    # 국제 통신사
    "reuters_world": "https://feeds.reuters.com/Reuters/worldNews",
    "ap_world": "https://rsshub.app/apnews/topics/world-news",
    "bbc_world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    # 분쟁 지역 전문
    "kyiv_independent": "https://kyivindependent.com/feed/",
    # 중동
    "iran_international_en": "https://www.iranintl.com/en/rss",
    "middleeasteye": "https://www.middleeasteye.net/rss",
}


@tool
def search_rss_feeds(
    query: str, feeds: list[str] | None = None, hours_back: int = 24
) -> list[dict]:
    """
    RSS 피드에서 뉴스를 검색합니다. 실시간 속보 확인에 유용합니다.

    Args:
        query: 검색어 (기사 제목/내용에서 검색)
        feeds: 검색할 피드 목록 (없으면 모든 피드 검색)
               가능한 값: reuters_world, ap_world, bbc_world, aljazeera,
                         kyiv_independent, iran_international_en, middleeasteye
        hours_back: 몇 시간 전까지 검색할지 (기본 24시간)

    Returns:
        매칭된 뉴스 목록
    """
    if feeds is None:
        feeds = list(RSS_FEEDS.keys())

    results = []
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
    query_lower = query.lower()

    for feed_name in feeds:
        if feed_name not in RSS_FEEDS:
            continue

        try:
            feed = feedparser.parse(RSS_FEEDS[feed_name])

            for entry in feed.entries[:20]:  # 최대 20개
                # 시간 필터
                published = entry.get("published_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff_time:
                        continue

                # 키워드 매칭
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                if query_lower in title.lower() or query_lower in summary.lower():
                    results.append(
                        {
                            "source_type": "rss",
                            "source_name": feed_name,
                            "title": title,
                            "content": summary[:500],  # 요약만
                            "url": entry.get("link", ""),
                            "published_at": str(pub_dt) if published else None,
                        }
                    )
        except Exception as e:
            logger.warning(f"RSS feed error ({feed_name}): {e}")

    return results


# ============================================================
# 텔레그램 도구
# ============================================================

# 주요 텔레그램 채널 (분쟁/시위 관련)
TELEGRAM_CHANNELS = {
    # 우크라이나
    "ukraine": [
        "ukrainenowenglish",
        "nexta_live",
        "UkraineNow",
    ],
    # 이란
    "iran": [
        "IranIntl",
        "IranHRM",
    ],
    # OSINT
    "osint": [
        "GeoConfirmed",
        "inikifo",
    ],
    # 중동
    "middle_east": [
        "QudsNen",
        "AJABreaking",
    ],
}


@tool
def search_telegram(
    query: str, region: str | None = None, limit: int = 10
) -> list[dict]:
    """
    텔레그램 채널에서 메시지를 검색합니다. 실시간 현장 영상/사진 수집에 유용합니다.

    Args:
        query: 검색어
        region: 지역 필터 (ukraine, iran, osint, middle_east 중 선택, 없으면 모든 채널)
        limit: 채널당 최대 메시지 수

    Returns:
        텔레그램 메시지 목록 (텍스트, 미디어 URL 포함)

    Note:
        텔레그램 API 초기화가 필요합니다. 세션이 없으면 빈 결과 반환.
    """
    # 동기 함수에서 비동기 호출을 위한 래퍼
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_search_telegram_async(query, region, limit))


async def _search_telegram_async(
    query: str, region: str | None, limit: int
) -> list[dict]:
    """텔레그램 검색 비동기 구현"""
    from telethon import TelegramClient

    # 채널 목록 결정
    if region and region in TELEGRAM_CHANNELS:
        channels = TELEGRAM_CHANNELS[region]
    else:
        channels = []
        for ch_list in TELEGRAM_CHANNELS.values():
            channels.extend(ch_list)

    results = []

    try:
        client = TelegramClient(
            "telegram_session",
            int(agent_settings.telegram_api_id),
            agent_settings.telegram_api_hash,
        )

        await client.start(phone=agent_settings.telegram_phone)

        for channel_name in channels[:5]:  # 최대 5개 채널 (비용/시간 절약)
            try:
                channel = await client.get_entity(channel_name)
                messages = await client.get_messages(channel, limit=limit)

                query_lower = query.lower()
                for msg in messages:
                    if not msg.text:
                        continue

                    if query_lower in msg.text.lower():
                        media_urls = []
                        if msg.media:
                            # 미디어 URL 추출 (실제로는 다운로드 필요)
                            media_urls.append(f"telegram://media/{channel_name}/{msg.id}")

                        results.append(
                            {
                                "source_type": "telegram",
                                "source_name": f"@{channel_name}",
                                "title": None,
                                "content": msg.text[:500],
                                "url": f"https://t.me/{channel_name}/{msg.id}",
                                "media_urls": media_urls,
                                "published_at": str(msg.date),
                            }
                        )
            except Exception as e:
                logger.warning(f"Telegram channel error ({channel_name}): {e}")

        await client.disconnect()

    except Exception as e:
        logger.error(f"Telegram client error: {e}")

    return results


# ============================================================
# 영상 도구
# ============================================================


@tool
def get_video_info(url: str) -> dict:
    """
    영상 URL에서 메타데이터를 추출합니다. YouTube, Twitter, Telegram 등 지원.

    Args:
        url: 영상 URL

    Returns:
        영상 정보 (제목, 설명, 업로더, 길이 등)
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,  # 다운로드 없이 정보만
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "source_type": "video",
                "source_name": info.get("extractor", "unknown"),
                "title": info.get("title", ""),
                "content": info.get("description", "")[:500] if info.get("description") else "",
                "url": url,
                "uploader": info.get("uploader", ""),
                "duration": info.get("duration"),
                "view_count": info.get("view_count"),
                "upload_date": info.get("upload_date"),
            }
    except Exception as e:
        logger.error(f"Video info error: {e}")
        return {"error": str(e)}


# ============================================================
# 번역 도구 (무료 API 사용)
# ============================================================


@tool
def translate_text(text: str, target_lang: str = "en") -> str:
    """
    텍스트를 번역합니다. 페르시아어, 아랍어, 러시아어 등을 영어로 번역할 때 사용.

    Args:
        text: 번역할 텍스트
        target_lang: 목표 언어 (기본: en)

    Returns:
        번역된 텍스트
    """
    try:
        # LibreTranslate 무료 API 사용
        response = httpx.post(
            "https://libretranslate.com/translate",
            json={
                "q": text[:1000],  # 길이 제한
                "source": "auto",
                "target": target_lang,
            },
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json().get("translatedText", text)
    except Exception as e:
        logger.warning(f"Translation error: {e}")

    return text  # 실패 시 원문 반환


# ============================================================
# 도구 목록 (에이전트에 제공)
# ============================================================

ALL_TOOLS = [
    search_web,
    search_rss_feeds,
    search_telegram,
    get_video_info,
    translate_text,
]
