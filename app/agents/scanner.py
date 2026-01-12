"""
자율 뉴스 스캐너 - GDELT 기반 키워드 글로벌 검색

특징:
- 소스 목록 하드코딩 없음 (RSS 피드 X)
- 키워드 기반으로 전 세계 100,000+ 소스 검색
- 15분 주기로 "war", "protest", "violence" 등 감지
- 에이전트가 소스를 정하는 게 아니라 키워드로 글로벌 검색
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Callable

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import agent_settings
from .models import EventCategory

logger = logging.getLogger(__name__)

# 감지할 키워드 (폭력/분쟁 관련)
TRIGGER_KEYWORDS = [
    # 전쟁/군사
    "war",
    "military operation",
    "airstrike",
    "missile strike",
    "invasion",
    "armed conflict",
    # 시위/불안
    "protest",
    "demonstration",
    "riot",
    "civil unrest",
    "uprising",
    # 테러/공격
    "terrorist attack",
    "bombing",
    "explosion",
    "hostage",
    # 폭력
    "violence",
    "massacre",
    "casualties",
    "killed",
]

# GDELT API 설정
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class NewsScanner:
    """
    자율 뉴스 스캐너 - GDELT 기반

    특징:
    - 소스 목록 지정 없이 키워드로 글로벌 검색
    - 100,000+ 뉴스 소스 자동 커버
    - 15분마다 업데이트되는 GDELT 데이터 활용
    """

    def __init__(self, on_event_detected: Callable | None = None):
        """
        Args:
            on_event_detected: 사건 감지 시 콜백 (event_description, category)
        """
        self.on_event_detected = on_event_detected
        self.seen_hashes: set[str] = set()  # 중복 방지
        self.last_scan: datetime | None = None

        # LLM (이벤트 분류용)
        self.llm = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=0.1,
            api_key=agent_settings.openai_api_key,
        )

    async def scan(self) -> list[dict]:
        """
        GDELT에서 키워드 기반 글로벌 검색

        Returns:
            감지된 중요 사건 목록
        """
        logger.info("Starting GDELT keyword scan...")
        self.last_scan = datetime.utcnow()

        # 1. GDELT API로 키워드 검색 (소스 지정 없음)
        all_articles = await self._search_gdelt()
        logger.info(f"GDELT returned {len(all_articles)} articles")

        # 2. 중복 제거
        new_articles = self._filter_duplicates(all_articles)
        logger.info(f"After dedup: {len(new_articles)} new articles")

        if not new_articles:
            return []

        # 3. LLM으로 중요 사건 분류
        significant_events = await self._classify_events(new_articles)
        logger.info(f"Significant events: {len(significant_events)}")

        # 4. 콜백 호출
        for event in significant_events:
            if self.on_event_detected:
                await self.on_event_detected(
                    event["description"], event["category"]
                )

        return significant_events

    async def _search_gdelt(self) -> list[dict]:
        """
        GDELT DOC API로 키워드 검색

        소스 목록 없이 키워드만으로 전 세계 검색
        """
        articles = []

        # 키워드 조합 (OR 연산 - 괄호 필수)
        keywords_str = " OR ".join(TRIGGER_KEYWORDS[:10])
        query = f"({keywords_str})"

        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": str(agent_settings.max_news_per_scan),
            "format": "json",
            "timespan": "1h",  # 최근 1시간
            "sort": "datedesc",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(GDELT_DOC_API, params=params)
                response.raise_for_status()

                data = response.json()
                raw_articles = data.get("articles", [])

                for art in raw_articles:
                    articles.append({
                        "title": art.get("title", ""),
                        "url": art.get("url", ""),
                        "source": art.get("domain", art.get("source", "unknown")),
                        "published": art.get("seendate", ""),
                        "language": art.get("language", "en"),
                        "country": art.get("sourcecountry", ""),
                        # GDELT이 자동으로 찾은 소스 (하드코딩 아님)
                    })

        except httpx.TimeoutException:
            logger.warning("GDELT API timeout")
        except Exception as e:
            logger.error(f"GDELT API error: {e}")

        return articles

    def _filter_duplicates(self, articles: list[dict]) -> list[dict]:
        """제목+URL 해시로 중복 제거"""
        new_articles = []

        for art in articles:
            content = f"{art['title']}:{art['url']}"
            hash_val = hashlib.md5(content.encode()).hexdigest()

            if hash_val not in self.seen_hashes:
                self.seen_hashes.add(hash_val)
                new_articles.append(art)

        # 메모리 관리
        if len(self.seen_hashes) > 10000:
            self.seen_hashes.clear()

        return new_articles

    async def _classify_events(self, articles: list[dict]) -> list[dict]:
        """LLM으로 중요 사건 분류 및 그룹화"""
        if not articles:
            return []

        # 배치로 분류 (비용 절약)
        articles_text = "\n".join([
            f"- [{art['source']}] {art['title']}"
            for art in articles[:30]  # 최대 30개
        ])

        system_prompt = """You are a breaking news analyst specializing in international conflicts.

Analyze these news headlines and identify SIGNIFICANT events.
Group related headlines into single events.

ONLY include events that are:
1. Breaking or developing (not old news)
2. Related to: war, armed conflict, protests, terrorism, military operations
3. Significant in scale or impact

For each significant event, respond in this EXACT format:
EVENT: [One sentence describing the event with location]
CATEGORY: [war|protest|terrorism|military|violence|civil_unrest|other]
SOURCES: [comma-separated source names that reported this]
CONFIDENCE: [high|medium|low]

If NO significant events found, respond with: NO_SIGNIFICANT_EVENTS

Important: Combine related headlines into ONE event. Don't list the same event multiple times."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Headlines to analyze:\n{articles_text}"),
            ])

            return self._parse_events(response.content, articles)

        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return []

    def _parse_events(self, response: str, original_articles: list[dict]) -> list[dict]:
        """LLM 응답 파싱"""
        if "NO_SIGNIFICANT_EVENTS" in response:
            return []

        events = []
        current_event = {}

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.startswith("EVENT:"):
                if current_event and "description" in current_event:
                    events.append(current_event)
                current_event = {"description": line[6:].strip()}

            elif line.startswith("CATEGORY:"):
                cat = line[9:].strip().lower()
                category_map = {
                    "war": "war",
                    "protest": "protest",
                    "terrorism": "terrorism",
                    "military": "military",
                    "violence": "violence",
                    "civil_unrest": "civil_unrest",
                }
                current_event["category"] = category_map.get(cat, "other")

            elif line.startswith("SOURCES:"):
                current_event["sources"] = [
                    s.strip() for s in line[8:].split(",")
                ]

            elif line.startswith("CONFIDENCE:"):
                current_event["confidence"] = line[11:].strip().lower()

        if current_event and "description" in current_event:
            events.append(current_event)

        return events

    def get_stats(self) -> dict:
        """스캐너 통계"""
        return {
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "seen_articles": len(self.seen_hashes),
            "trigger_keywords": len(TRIGGER_KEYWORDS),
        }


async def run_scanner_test():
    """테스트: 스캐너 1회 실행"""
    print("\n" + "=" * 60)
    print("🔍 GDELT KEYWORD SCANNER TEST")
    print("=" * 60)
    print(f"Keywords: {TRIGGER_KEYWORDS[:5]}...")
    print("Searching globally (NO predefined sources)")
    print("=" * 60 + "\n")

    detected_events = []

    async def on_event(description: str, category: str):
        detected_events.append((description, category))
        print(f"\n🚨 EVENT DETECTED!")
        print(f"   Category: {category}")
        print(f"   Description: {description}")

    scanner = NewsScanner(on_event_detected=on_event)
    events = await scanner.scan()

    print(f"\n📊 Scan Results:")
    print(f"   Total events detected: {len(events)}")
    print(f"   Stats: {scanner.get_stats()}")

    if events:
        print(f"\n📋 Event Details:")
        for i, event in enumerate(events, 1):
            print(f"\n   [{i}] {event.get('description', 'N/A')}")
            print(f"       Category: {event.get('category', 'N/A')}")
            print(f"       Sources: {', '.join(event.get('sources', []))}")
            print(f"       Confidence: {event.get('confidence', 'N/A')}")

    return events


if __name__ == "__main__":
    asyncio.run(run_scanner_test())
