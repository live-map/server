"""
뉴스 스캐너 - 15-30분 주기로 국제 정세 뉴스 모니터링

폭력(전쟁, 시위, 테러 등) 관련 중요 사건을 감지하여 조사 에이전트 트리거
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable

import feedparser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import agent_settings
from .models import EventCategory

logger = logging.getLogger(__name__)

# 모니터링할 RSS 피드
MONITOR_FEEDS = {
    "reuters_world": "https://feeds.reuters.com/Reuters/worldNews",
    "bbc_world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "iran_international": "https://www.iranintl.com/en/rss",
}

# 폭력/분쟁 관련 키워드 (1차 필터)
VIOLENCE_KEYWORDS = [
    # 전쟁
    "war",
    "conflict",
    "military",
    "troops",
    "invasion",
    "strike",
    "bombing",
    "missile",
    "drone",
    "attack",
    "offensive",
    "frontline",
    # 시위
    "protest",
    "demonstration",
    "riot",
    "unrest",
    "uprising",
    "revolution",
    "crackdown",
    # 테러
    "terrorism",
    "terrorist",
    "explosion",
    "bomb",
    "hostage",
    # 폭력
    "violence",
    "killed",
    "casualties",
    "wounded",
    "dead",
    "massacre",
    "shooting",
    # 긴급
    "breaking",
    "urgent",
    "emergency",
]


class NewsScanner:
    """
    뉴스 스캐너 - 주기적으로 뉴스를 스캔하고 중요 사건 감지
    """

    def __init__(self, on_event_detected: Callable | None = None):
        """
        Args:
            on_event_detected: 사건 감지 시 호출할 콜백 함수
                               (event_description, category) -> None
        """
        self.on_event_detected = on_event_detected
        self.seen_urls: set[str] = set()  # 이미 처리한 URL
        self.last_scan: datetime | None = None

        # LLM (저렴한 모델)
        self.llm = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=0.1,  # 분류는 낮은 온도
            api_key=agent_settings.openai_api_key,
        )

    async def scan(self) -> list[dict]:
        """
        모든 소스에서 뉴스 스캔

        Returns:
            감지된 중요 사건 목록
        """
        logger.info("Starting news scan...")
        self.last_scan = datetime.utcnow()

        # 1. RSS 피드에서 뉴스 수집
        all_news = await self._collect_from_rss()
        logger.info(f"Collected {len(all_news)} news items from RSS")

        # 2. 키워드 기반 1차 필터
        filtered = self._keyword_filter(all_news)
        logger.info(f"After keyword filter: {len(filtered)} items")

        # 3. LLM으로 중요 사건 분류
        significant_events = await self._classify_significance(filtered)
        logger.info(f"Significant events detected: {len(significant_events)}")

        # 4. 콜백 호출
        for event in significant_events:
            if self.on_event_detected:
                await self.on_event_detected(
                    event["description"], event["category"]
                )

        return significant_events

    async def _collect_from_rss(self) -> list[dict]:
        """RSS 피드에서 뉴스 수집"""
        news_items = []
        cutoff = datetime.utcnow() - timedelta(hours=1)  # 최근 1시간

        for feed_name, feed_url in MONITOR_FEEDS.items():
            try:
                feed = feedparser.parse(feed_url)

                for entry in feed.entries[:20]:
                    url = entry.get("link", "")

                    # 이미 본 URL 스킵
                    if url in self.seen_urls:
                        continue
                    self.seen_urls.add(url)

                    # 시간 필터
                    published = entry.get("published_parsed")
                    if published:
                        pub_dt = datetime(*published[:6])
                        if pub_dt < cutoff:
                            continue

                    news_items.append(
                        {
                            "source": feed_name,
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", "")[:500],
                            "url": url,
                            "published": str(pub_dt) if published else None,
                        }
                    )
            except Exception as e:
                logger.warning(f"RSS error ({feed_name}): {e}")

        return news_items

    def _keyword_filter(self, news_items: list[dict]) -> list[dict]:
        """키워드 기반 1차 필터 (비용 절약)"""
        filtered = []

        for item in news_items:
            text = f"{item['title']} {item['summary']}".lower()

            for keyword in VIOLENCE_KEYWORDS:
                if keyword in text:
                    filtered.append(item)
                    break

        return filtered

    async def _classify_significance(self, news_items: list[dict]) -> list[dict]:
        """LLM으로 중요 사건 분류"""
        if not news_items:
            return []

        # 비용 절약: 배치로 처리
        news_text = "\n".join(
            [f"- [{item['source']}] {item['title']}" for item in news_items[:20]]
        )

        system_prompt = """You are a news analyst specializing in international conflicts and violence.
Analyze the following news headlines and identify SIGNIFICANT events related to:
- Wars and armed conflicts
- Protests and civil unrest
- Terrorism and attacks
- Military operations

For each significant event, respond in this exact format:
EVENT: [Brief description in one sentence]
CATEGORY: [war|protest|terrorism|military|violence|civil_unrest]
SOURCES: [comma-separated source names]

Only include events that are:
1. Breaking or developing (not old news)
2. Significant in scale or impact
3. Related to violence, conflict, or civil unrest

If no significant events, respond with: NO_SIGNIFICANT_EVENTS"""

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"News headlines:\n{news_text}"),
                ]
            )

            return self._parse_classification(response.content, news_items)

        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return []

    def _parse_classification(
        self, response: str, original_items: list[dict]
    ) -> list[dict]:
        """LLM 응답 파싱"""
        if "NO_SIGNIFICANT_EVENTS" in response:
            return []

        events = []
        current_event = {}

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.startswith("EVENT:"):
                if current_event:
                    events.append(current_event)
                current_event = {"description": line[6:].strip()}

            elif line.startswith("CATEGORY:"):
                category = line[9:].strip().lower()
                # EventCategory에 매핑
                category_map = {
                    "war": "war",
                    "protest": "protest",
                    "terrorism": "terrorism",
                    "military": "military",
                    "violence": "violence",
                    "civil_unrest": "civil_unrest",
                }
                current_event["category"] = category_map.get(category, "other")

            elif line.startswith("SOURCES:"):
                current_event["sources"] = [
                    s.strip() for s in line[8:].split(",")
                ]

        if current_event and "description" in current_event:
            events.append(current_event)

        return events

    def cleanup_seen_urls(self, max_age_hours: int = 24):
        """오래된 URL 정리 (메모리 관리)"""
        # 간단히 전체 삭제 (프로덕션에서는 시간 기반 만료 구현)
        if len(self.seen_urls) > 10000:
            self.seen_urls.clear()


async def run_scanner_once():
    """테스트용: 스캐너 1회 실행"""

    async def on_event(description: str, category: str):
        print(f"\n🚨 EVENT DETECTED!")
        print(f"   Category: {category}")
        print(f"   Description: {description}")

    scanner = NewsScanner(on_event_detected=on_event)
    events = await scanner.scan()

    print(f"\n📊 Scan complete. {len(events)} significant events found.")
    return events


if __name__ == "__main__":
    asyncio.run(run_scanner_once())
