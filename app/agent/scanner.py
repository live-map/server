"""
다중 소스 뉴스 스캐너

트리거 소스:
1. GDELT - 뉴스 (무료, 100,000+ 소스)
2. X/Twitter - 실시간 (Twikit, 개인계정)
3. Telegram - 실시간 (Telethon, 가입채널)

특징:
- 소스 하드코딩 없음
- 키워드 기반 글로벌 검색
- 에이전트가 소스를 결정하지 않음 - 모든 소스에서 자동 수집
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import agent_settings
from .triggers import TriggerEvent, TriggerManager

logger = logging.getLogger(__name__)


class MultiSourceScanner:
    """
    다중 소스 스캐너

    GDELT + X/Twitter + Telegram에서 동시 모니터링
    """

    def __init__(self, on_event_detected: Callable | None = None):
        """
        Args:
            on_event_detected: 사건 감지 시 콜백 (event_description, category)
        """
        self.on_event_detected = on_event_detected
        self.trigger_manager = self._create_trigger_manager()
        self.last_scan: datetime | None = None

        # LLM (최종 분류용)
        if agent_settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=agent_settings.llm_model,
                temperature=0.1,
                api_key=agent_settings.openai_api_key,
            )
        else:
            self.llm = None

    def _create_trigger_manager(self) -> TriggerManager:
        """설정 기반 트리거 매니저 생성"""
        manager = TriggerManager(
            openai_api_key=agent_settings.openai_api_key,
            llm_model=agent_settings.llm_model,
        )

        # GDELT (기본 활성화)
        if agent_settings.gdelt_enabled:
            manager.add_gdelt(timespan=agent_settings.gdelt_timespan)
            logger.info("GDELT trigger added")

        # X/Twitter (설정 시 활성화)
        if agent_settings.twitter_enabled and agent_settings.twitter_username:
            manager.add_twitter(
                username=agent_settings.twitter_username,
                email=agent_settings.twitter_email,
                password=agent_settings.twitter_password,
                cookies_path=agent_settings.twitter_cookies_path,
            )
            logger.info("X/Twitter trigger added")

        # Telegram (설정 시 활성화)
        if agent_settings.telegram_enabled and agent_settings.telegram_api_id:
            channels = agent_settings.get_telegram_channels()
            manager.add_telegram(
                api_id=agent_settings.telegram_api_id,
                api_hash=agent_settings.telegram_api_hash,
                phone=agent_settings.telegram_phone,
                channels=channels if channels else None,
            )
            logger.info(f"Telegram trigger added ({len(channels) if channels else 'default'} channels)")

        return manager

    async def initialize(self) -> dict[str, bool]:
        """모든 트리거 초기화"""
        return await self.trigger_manager.initialize_all()

    async def scan(self) -> list[dict]:
        """
        모든 소스에서 스캔

        Returns:
            감지된 중요 사건 목록
        """
        logger.info("Starting multi-source scan...")
        self.last_scan = datetime.utcnow()

        # 모든 트리거에서 병렬 스캔
        events = await self.trigger_manager.scan_all()

        if not events:
            logger.info("No events detected")
            return []

        # LLM으로 최종 분류 및 그룹화
        significant_events = await self._classify_and_group(events)
        logger.info(f"Significant events: {len(significant_events)}")

        # 콜백 호출
        for event in significant_events:
            if self.on_event_detected:
                await self._safe_callback(
                    event["description"],
                    event["category"],
                )

        return significant_events

    async def _classify_and_group(self, events: list[TriggerEvent]) -> list[dict]:
        """LLM으로 이벤트 분류 및 그룹화"""
        if not events or not self.llm:
            # LLM 없으면 기본 형식으로 변환
            return [
                {
                    "description": e.title,
                    "category": "other",
                    "sources": [e.source_name],
                    "trigger_source": e.source.value,
                    "keywords": e.keywords_matched,
                }
                for e in events
            ]

        # 배치로 분류
        events_text = "\n".join([
            f"- [{e.source.value}:{e.source_name}] {e.title}"
            for e in events[:40]
        ])

        system_prompt = """You are a breaking news analyst specializing in international conflicts.

Analyze these events from multiple sources (news, Twitter, Telegram).
Group related events into single incidents.

Categories:
- war: Armed conflicts, military operations, airstrikes
- protest: Demonstrations, civil unrest, riots
- terrorism: Terrorist attacks, bombings
- military: Military movements, exercises
- violence: General violence, casualties
- other: Not fitting above

For each SIGNIFICANT event, respond:
EVENT: [One sentence description with location]
CATEGORY: [category]
SOURCES: [list of sources that reported this]
CONFIDENCE: [high/medium/low]

Combine related news from different sources into ONE event.
Only include breaking/significant events, not routine news.

If no significant events: NO_SIGNIFICANT_EVENTS"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Events from multiple sources:\n{events_text}"),
            ])

            return self._parse_classification(response.content, events)

        except Exception as e:
            logger.error(f"Classification error: {e}")
            return []

    def _parse_classification(
        self, response: str, original_events: list[TriggerEvent]
    ) -> list[dict]:
        """분류 결과 파싱"""
        if "NO_SIGNIFICANT_EVENTS" in response:
            return []

        results = []
        current_event = {}

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.startswith("EVENT:"):
                if current_event and "description" in current_event:
                    results.append(current_event)
                current_event = {"description": line[6:].strip()}

            elif line.startswith("CATEGORY:"):
                current_event["category"] = line[9:].strip().lower()

            elif line.startswith("SOURCES:"):
                sources_text = line[8:].strip()
                current_event["sources"] = [s.strip() for s in sources_text.split(",")]

            elif line.startswith("CONFIDENCE:"):
                current_event["confidence"] = line[11:].strip().lower()

        if current_event and "description" in current_event:
            results.append(current_event)

        return results

    async def _safe_callback(self, description: str, category: str):
        """안전한 콜백 호출"""
        try:
            if asyncio.iscoroutinefunction(self.on_event_detected):
                await self.on_event_detected(description, category)
            else:
                self.on_event_detected(description, category)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def close(self):
        """리소스 정리"""
        await self.trigger_manager.close_all()

    def get_status(self) -> dict:
        """스캐너 상태"""
        return {
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "triggers": self.trigger_manager.get_status(),
        }


# 하위 호환성을 위한 별칭
NewsScanner = MultiSourceScanner


async def run_scanner_test():
    """테스트: 다중 소스 스캐너 실행"""
    print("\n" + "=" * 70)
    print("🔔 MULTI-SOURCE SCANNER TEST")
    print("=" * 70)
    print("Sources: GDELT (news) + X/Twitter + Telegram")
    print("=" * 70 + "\n")

    detected_events = []

    async def on_event(description: str, category: str):
        detected_events.append((description, category))
        print(f"\n🚨 EVENT DETECTED!")
        print(f"   Category: {category}")
        print(f"   Description: {description}")

    scanner = MultiSourceScanner(on_event_detected=on_event)

    # 초기화
    print("Initializing triggers...")
    results = await scanner.initialize()
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    # 스캔
    print("\nScanning all sources...")
    events = await scanner.scan()

    print(f"\n📊 Results:")
    print(f"   Events detected: {len(detected_events)}")

    if events:
        print(f"\n📋 Event Details:")
        for i, event in enumerate(events, 1):
            print(f"\n   [{i}] {event.get('description', 'N/A')}")
            print(f"       Category: {event.get('category', 'N/A')}")
            print(f"       Sources: {', '.join(event.get('sources', []))}")

    print(f"\n🔧 Scanner Status: {scanner.get_status()}")

    await scanner.close()
    return events


if __name__ == "__main__":
    asyncio.run(run_scanner_test())
