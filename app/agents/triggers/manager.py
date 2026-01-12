"""
통합 트리거 매니저

여러 트리거 소스를 통합 관리:
- GDELT (뉴스, 15분 딜레이)
- X/Twitter (실시간)
- Telegram (실시간)

모든 소스에서 병렬로 이벤트 수집 후 중복 제거 및 통합
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .base import BaseTrigger, TriggerEvent, TriggerSource
from .gdelt import GDELTTrigger
from .telegram import TelegramTrigger
from .twitter import TwitterTrigger

logger = logging.getLogger(__name__)


class TriggerManager:
    """
    다중 트리거 소스 통합 관리자

    특징:
    - 여러 소스에서 병렬 스캔
    - 중복 이벤트 제거 (동일 사건 다른 소스)
    - LLM으로 이벤트 분류 및 그룹화
    - 콜백으로 이벤트 전달
    """

    def __init__(
        self,
        on_event: Callable[[TriggerEvent, str], None] | None = None,
        openai_api_key: str | None = None,
        llm_model: str = "gpt-4o-mini",
    ):
        """
        Args:
            on_event: 이벤트 감지 시 콜백 (event, category)
            openai_api_key: OpenAI API 키 (이벤트 분류용)
            llm_model: 사용할 LLM 모델
        """
        self.on_event = on_event
        self.triggers: list[BaseTrigger] = []
        self.last_scan: datetime | None = None
        self.event_hashes: set[str] = set()  # 중복 방지

        # LLM (이벤트 분류용)
        if openai_api_key:
            self.llm = ChatOpenAI(
                model=llm_model,
                temperature=0.1,
                api_key=openai_api_key,
            )
        else:
            self.llm = None

    def add_trigger(self, trigger: BaseTrigger):
        """트리거 소스 추가"""
        self.triggers.append(trigger)
        logger.info(f"Added trigger: {trigger.source_name}")

    def add_gdelt(
        self,
        keywords: list[str] | None = None,
        timespan: str = "1h",
    ) -> "TriggerManager":
        """GDELT 트리거 추가 (체이닝)"""
        self.add_trigger(GDELTTrigger(
            keywords=keywords,
            timespan=timespan,
        ))
        return self

    def add_twitter(
        self,
        username: str,
        email: str,
        password: str,
        cookies_path: str | None = None,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """Twitter 트리거 추가 (체이닝)"""
        self.add_trigger(TwitterTrigger(
            username=username,
            email=email,
            password=password,
            cookies_path=cookies_path,
            keywords=keywords,
        ))
        return self

    def add_telegram(
        self,
        api_id: str,
        api_hash: str,
        phone: str,
        channels: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """Telegram 트리거 추가 (체이닝)"""
        self.add_trigger(TelegramTrigger(
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            channels=channels,
            keywords=keywords,
        ))
        return self

    async def initialize_all(self) -> dict[str, bool]:
        """모든 트리거 초기화"""
        results = {}
        for trigger in self.triggers:
            try:
                success = await trigger.initialize()
                results[trigger.source_name] = success
            except Exception as e:
                logger.error(f"Failed to initialize {trigger.source_name}: {e}")
                results[trigger.source_name] = False
        return results

    async def scan_all(self) -> list[TriggerEvent]:
        """
        모든 트리거에서 병렬 스캔

        Returns:
            중복 제거된 이벤트 목록
        """
        self.last_scan = datetime.utcnow()
        all_events: list[TriggerEvent] = []

        # 병렬 스캔
        tasks = []
        for trigger in self.triggers:
            if trigger.is_initialized:
                tasks.append(self._scan_trigger(trigger))

        if not tasks:
            logger.warning("No initialized triggers to scan")
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scan error: {result}")
            elif isinstance(result, list):
                all_events.extend(result)

        # 중복 제거
        unique_events = self._deduplicate_events(all_events)
        logger.info(f"Total events: {len(all_events)}, unique: {len(unique_events)}")

        # LLM으로 분류 (선택적)
        if unique_events and self.llm:
            classified = await self._classify_events(unique_events)

            # 콜백 호출
            for event, category in classified:
                if self.on_event:
                    await self._safe_callback(event, category)

            return [e for e, _ in classified]

        return unique_events

    async def _scan_trigger(self, trigger: BaseTrigger) -> list[TriggerEvent]:
        """단일 트리거 스캔 (에러 핸들링)"""
        try:
            return await trigger.scan()
        except Exception as e:
            logger.error(f"Error scanning {trigger.source_name}: {e}")
            return []

    def _deduplicate_events(self, events: list[TriggerEvent]) -> list[TriggerEvent]:
        """
        중복 이벤트 제거

        동일한 사건이 여러 소스에서 감지될 수 있음
        제목 유사도로 중복 판단
        """
        unique = []
        seen_titles = set()

        for event in events:
            # 제목 정규화 (소문자, 공백 제거)
            normalized = event.title.lower().strip()[:100]
            title_hash = hashlib.md5(normalized.encode()).hexdigest()

            if title_hash not in seen_titles:
                seen_titles.add(title_hash)

                # 전체 해시로도 체크 (더 정확)
                event_hash = hashlib.md5(
                    f"{event.title}:{event.url}".encode()
                ).hexdigest()

                if event_hash not in self.event_hashes:
                    self.event_hashes.add(event_hash)
                    unique.append(event)

        # 메모리 관리
        if len(self.event_hashes) > 10000:
            self.event_hashes.clear()

        return unique

    async def _classify_events(
        self, events: list[TriggerEvent]
    ) -> list[tuple[TriggerEvent, str]]:
        """LLM으로 이벤트 분류"""
        if not events:
            return []

        # 배치로 분류
        events_text = "\n".join([
            f"- [{e.source.value}:{e.source_name}] {e.title}"
            for e in events[:30]
        ])

        system_prompt = """You are a breaking news analyst.
Classify these events into categories.

Categories:
- war: Armed conflicts, military operations
- protest: Demonstrations, civil unrest
- terrorism: Terrorist attacks, explosions
- military: Military movements, exercises
- violence: General violence, casualties
- other: Not fitting above categories

For each event, respond:
INDEX: [0-based index]
CATEGORY: [category]
SIGNIFICANT: [yes/no]

Only include SIGNIFICANT events (major breaking news)."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Events:\n{events_text}"),
            ])

            return self._parse_classification(response.content, events)

        except Exception as e:
            logger.error(f"Classification error: {e}")
            # 분류 실패 시 모두 'other'로
            return [(e, "other") for e in events]

    def _parse_classification(
        self, response: str, events: list[TriggerEvent]
    ) -> list[tuple[TriggerEvent, str]]:
        """분류 결과 파싱"""
        classified = []
        current_idx = None
        current_category = None
        current_significant = False

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.startswith("INDEX:"):
                if current_idx is not None and current_significant:
                    if 0 <= current_idx < len(events):
                        classified.append((events[current_idx], current_category or "other"))

                try:
                    current_idx = int(line.split(":")[1].strip())
                except:
                    current_idx = None
                current_category = None
                current_significant = False

            elif line.startswith("CATEGORY:"):
                current_category = line.split(":")[1].strip().lower()

            elif line.startswith("SIGNIFICANT:"):
                current_significant = "yes" in line.lower()

        # 마지막 항목
        if current_idx is not None and current_significant:
            if 0 <= current_idx < len(events):
                classified.append((events[current_idx], current_category or "other"))

        return classified

    async def _safe_callback(self, event: TriggerEvent, category: str):
        """안전한 콜백 호출"""
        try:
            if asyncio.iscoroutinefunction(self.on_event):
                await self.on_event(event, category)
            else:
                self.on_event(event, category)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def close_all(self):
        """모든 트리거 종료"""
        for trigger in self.triggers:
            try:
                await trigger.close()
            except Exception as e:
                logger.error(f"Error closing {trigger.source_name}: {e}")

    def get_status(self) -> dict:
        """트리거 상태 반환"""
        return {
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "triggers": [
                {
                    "name": t.source_name,
                    "type": t.source_type.value,
                    "initialized": t.is_initialized,
                    "last_scan": t.last_scan.isoformat() if t.last_scan else None,
                }
                for t in self.triggers
            ],
            "event_count": len(self.event_hashes),
        }


async def test_trigger_manager():
    """테스트: 트리거 매니저 실행"""
    print("\n" + "=" * 60)
    print("🔔 MULTI-SOURCE TRIGGER TEST")
    print("=" * 60)

    events_detected = []

    async def on_event(event: TriggerEvent, category: str):
        events_detected.append((event, category))
        print(f"\n🚨 [{event.source.value}] {category.upper()}")
        print(f"   {event.title[:80]}...")
        print(f"   Source: {event.source_name}")
        print(f"   Keywords: {', '.join(event.keywords_matched)}")

    # 매니저 생성 (GDELT만 테스트 - API 키 불필요)
    manager = TriggerManager(on_event=on_event)
    manager.add_gdelt(timespan="24h")

    # 초기화
    print("\nInitializing triggers...")
    results = await manager.initialize_all()
    for name, success in results.items():
        print(f"  {name}: {'✅' if success else '❌'}")

    # 스캔
    print("\nScanning...")
    events = await manager.scan_all()

    print(f"\n📊 Results:")
    print(f"   Events detected: {len(events_detected)}")
    print(f"   Status: {manager.get_status()}")

    await manager.close_all()
    return events


if __name__ == "__main__":
    asyncio.run(test_trigger_manager())
