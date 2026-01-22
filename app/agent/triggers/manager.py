"""
통합 트리거 매니저

여러 트리거 소스를 통합 관리:
- GDELT (뉴스, 15분 딜레이)
- X/Twitter (실시간)
- Telegram (실시간)

감지 레이어:
- Anomaly Detection: 볼륨/속도 이상 감지 (키워드 무관)
- Semantic Clustering: 새로운 주제 클러스터 감지

모든 소스에서 병렬로 이벤트 수집 후 중복 제거 및 통합
"""

import asyncio
import hashlib
import logging
import time
from collections import Counter
from datetime import datetime
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .base import BaseTrigger, TriggerEvent, TriggerSource
from .gdelt import GDELTTrigger
from .telegram import TelegramTrigger
from .twitter import TwitterTrigger
from .anomaly import AnomalyDetector, AnomalySignal
from .clustering import SemanticClusterer, ClusteringSignal

# Multi-source triggers (Phase 1-4)
from .gdelt_anomaly import GDELTAnomalyTrigger
from .reddit import RedditTrigger
from .bluesky import BlueskyTrigger
from .google_trends import GoogleTrendsTrigger
from .currents import CurrentsTrigger
from .worldnews import WorldNewsTrigger
from .usgs import USGSTrigger
from .noaa import NOAATrigger
from .acled import ACLEDTrigger

logger = logging.getLogger(__name__)


class TriggerManager:
    """
    다중 트리거 소스 통합 관리자

    특징:
    - 여러 소스에서 병렬 스캔
    - 중복 이벤트 제거 (동일 사건 다른 소스)
    - LLM으로 이벤트 분류 및 그룹화
    - 콜백으로 이벤트 전달

    감지 레이어:
    - Anomaly Detection: 볼륨/속도 이상 감지
    - Semantic Clustering: 새로운 주제 클러스터 감지
    """

    def __init__(
        self,
        on_event: Callable[[TriggerEvent, str], None] | None = None,
        on_anomaly: Callable[[AnomalySignal], None] | None = None,
        on_new_cluster: Callable[[ClusteringSignal], None] | None = None,
        openai_api_key: str | None = None,
        llm_model: str = "gpt-4o-mini",
        enable_anomaly_detection: bool = True,
        enable_clustering: bool = True,
    ):
        """
        Args:
            on_event: 이벤트 감지 시 콜백 (event, category)
            on_anomaly: 이상 감지 시 콜백 (anomaly_signal)
            on_new_cluster: 새 클러스터 감지 시 콜백 (clustering_signal)
            openai_api_key: OpenAI API 키 (이벤트 분류용)
            llm_model: 사용할 LLM 모델
            enable_anomaly_detection: 이상 감지 활성화
            enable_clustering: 클러스터링 활성화
        """
        self.on_event = on_event
        self.on_anomaly = on_anomaly
        self.on_new_cluster = on_new_cluster
        self.triggers: list[BaseTrigger] = []
        self.last_scan: datetime | None = None
        # 중복 방지 - dict[hash, timestamp] for time-based expiry
        self.event_hashes: dict[str, float] = {}
        self.hash_expiry_seconds: float = 86400  # 24 hours

        # LLM (이벤트 분류용)
        if openai_api_key:
            self.llm = ChatOpenAI(
                model=llm_model,
                temperature=0.1,
                api_key=openai_api_key,
            )
        else:
            self.llm = None

        # 감지 레이어
        self.enable_anomaly_detection = enable_anomaly_detection
        self.enable_clustering = enable_clustering

        self.anomaly_detector = AnomalyDetector(
            short_window=10,
            long_window=50,
            z_threshold=2.5,  # 2.5 시그마 (약간 민감하게)
        ) if enable_anomaly_detection else None

        self.semantic_clusterer = SemanticClusterer(
            similarity_threshold=0.7,
            new_cluster_threshold=0.4,
            min_cluster_size=2,
        ) if enable_clustering else None

        self._clustering_initialized = False

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

    # ============================================
    # Multi-Source Triggers (Phase 1-4)
    # ============================================

    def add_gdelt_anomaly(
        self,
        keywords: list[str] | None = None,
        timespan: str = "15min",
        goldstein_threshold: float = -5.0,
    ) -> "TriggerManager":
        """GDELT Anomaly Detection 트리거 추가 (Tier-1)"""
        self.add_trigger(GDELTAnomalyTrigger(
            keywords=keywords,
            timespan=timespan,
            goldstein_threshold=goldstein_threshold,
        ))
        return self

    def add_reddit(
        self,
        subreddits: list[str] | None = None,
        min_score: int = 50,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """Reddit 트리거 추가 (Tier-3)"""
        self.add_trigger(RedditTrigger(
            subreddits=subreddits,
            min_score=min_score,
            keywords=keywords,
        ))
        return self

    def add_bluesky(
        self,
        min_likes: int = 10,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """Bluesky 트리거 추가 (Tier-3)"""
        self.add_trigger(BlueskyTrigger(
            min_likes=min_likes,
            keywords=keywords,
        ))
        return self

    def add_google_trends(
        self,
        geo: str = "US",
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """Google Trends 트리거 추가 (Tier-3)"""
        self.add_trigger(GoogleTrendsTrigger(
            geo=geo,
            keywords=keywords,
        ))
        return self

    def add_currents(
        self,
        api_key: str,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """Currents API 트리거 추가 (Tier-2)"""
        self.add_trigger(CurrentsTrigger(
            api_key=api_key,
            keywords=keywords,
        ))
        return self

    def add_worldnews(
        self,
        api_key: str,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """World News API 트리거 추가 (Tier-2)"""
        self.add_trigger(WorldNewsTrigger(
            api_key=api_key,
            keywords=keywords,
        ))
        return self

    def add_usgs(
        self,
        min_magnitude: float = 5.0,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """USGS Earthquake 트리거 추가 (Tier-1)"""
        self.add_trigger(USGSTrigger(
            min_magnitude=min_magnitude,
            keywords=keywords,
        ))
        return self

    def add_noaa(
        self,
        severity: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """NOAA Weather 트리거 추가 (Tier-1)"""
        self.add_trigger(NOAATrigger(
            severity=severity,
            keywords=keywords,
        ))
        return self

    def add_acled(
        self,
        api_key: str,
        email: str,
        event_types: list[str] | None = None,
        min_fatalities: int = 0,
        keywords: list[str] | None = None,
    ) -> "TriggerManager":
        """ACLED Conflict 트리거 추가 (Tier-2)"""
        self.add_trigger(ACLEDTrigger(
            api_key=api_key,
            email=email,
            event_types=event_types,
            min_fatalities=min_fatalities,
            keywords=keywords,
        ))
        return self

    async def initialize_all(self) -> dict[str, bool]:
        """모든 트리거 및 감지 레이어 초기화"""
        results = {}

        # 트리거 초기화
        for trigger in self.triggers:
            try:
                success = await trigger.initialize()
                results[trigger.source_name] = success
            except Exception as e:
                logger.error(f"Failed to initialize {trigger.source_name}: {e}")
                results[trigger.source_name] = False

        # Semantic Clusterer 초기화 (임베딩 모델 로딩)
        if self.semantic_clusterer and not self._clustering_initialized:
            try:
                success = await self.semantic_clusterer.initialize()
                results["semantic_clusterer"] = success
                self._clustering_initialized = success
                if success:
                    logger.info("Semantic clusterer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize semantic clusterer: {e}")
                results["semantic_clusterer"] = False

        # Anomaly Detector는 상태 없으므로 항상 성공
        if self.anomaly_detector:
            results["anomaly_detector"] = True

        return results

    async def scan_all(
        self,
        sources: list[str] | None = None,
    ) -> list[TriggerEvent]:
        """
        모든 트리거에서 병렬 스캔 + 감지 레이어 실행

        Args:
            sources: 스캔할 소스 목록 (gdelt, twitter, telegram). None이면 모든 소스.

        Returns:
            중복 제거된 이벤트 목록
        """
        self.last_scan = datetime.utcnow()
        all_events: list[TriggerEvent] = []

        # 병렬 스캔
        tasks = []
        for trigger in self.triggers:
            if not trigger.is_initialized:
                continue
            # 소스 필터링
            if sources and trigger.source_type.value.lower() not in [s.lower() for s in sources]:
                continue
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

        # ============================================
        # 감지 레이어 1: Anomaly Detection
        # ============================================
        if self.anomaly_detector:
            await self._run_anomaly_detection(unique_events)

        # ============================================
        # 감지 레이어 2: Semantic Clustering
        # ============================================
        if self.semantic_clusterer and self._clustering_initialized:
            await self._run_semantic_clustering(unique_events)

        # LLM으로 분류 (선택적)
        if unique_events and self.llm:
            classified = await self._classify_events(unique_events)

            # 콜백 호출
            for event, category in classified:
                if self.on_event:
                    await self._safe_callback(event, category)

            return [e for e, _ in classified]

        return unique_events

    async def _run_anomaly_detection(self, events: list[TriggerEvent]):
        """이상 감지 레이어 실행"""
        # 소스별 카운트
        source_counts = Counter(e.source.value for e in events)

        # 키워드별 카운트
        keyword_counts: dict[str, int] = {}
        for event in events:
            for kw in event.keywords_matched:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        # 이상 감지
        anomalies = self.anomaly_detector.record_scan(
            event_count=len(events),
            source_counts=dict(source_counts),
            keyword_counts=keyword_counts,
        )

        # 콜백 호출
        for anomaly in anomalies:
            if self.on_anomaly:
                try:
                    if asyncio.iscoroutinefunction(self.on_anomaly):
                        await self.on_anomaly(anomaly)
                    else:
                        self.on_anomaly(anomaly)
                except Exception as e:
                    logger.error(f"Anomaly callback error: {e}")

    async def _run_semantic_clustering(self, events: list[TriggerEvent]):
        """의미적 클러스터링 레이어 실행"""
        if not events:
            return

        # 이벤트를 문서 형태로 변환
        documents = [
            {
                "title": e.title,
                "content": e.content,
                "url": e.url,
                "source": e.source.value,
            }
            for e in events
        ]

        # 클러스터링 실행
        try:
            signals = await self.semantic_clusterer.process_documents(documents)

            # 콜백 호출
            for signal in signals:
                if self.on_new_cluster:
                    try:
                        if asyncio.iscoroutinefunction(self.on_new_cluster):
                            await self.on_new_cluster(signal)
                        else:
                            self.on_new_cluster(signal)
                    except Exception as e:
                        logger.error(f"Clustering callback error: {e}")

        except Exception as e:
            logger.error(f"Semantic clustering error: {e}")

    async def _scan_trigger(self, trigger: BaseTrigger) -> list[TriggerEvent]:
        """단일 트리거 스캔 (에러 핸들링)"""
        try:
            return await trigger.scan()
        except Exception as e:
            logger.error(f"Error scanning {trigger.source_name}: {e}")
            return []

    def _deduplicate_events(self, events: list[TriggerEvent]) -> list[TriggerEvent]:
        """
        중복 이벤트 제거 (시간 기반 만료)

        동일한 사건이 여러 소스에서 감지될 수 있음
        제목 유사도로 중복 판단
        """
        current_time = time.time()
        unique = []
        seen_titles = set()

        # 먼저 만료된 해시 정리
        self._cleanup_expired_hashes(current_time)

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
                    self.event_hashes[event_hash] = current_time
                    unique.append(event)

        return unique

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """만료된 해시 정리 (24시간 이상 된 항목 제거)"""
        if len(self.event_hashes) > 5000:
            # 메모리 임계치 초과 시 정리
            expired = [
                h for h, ts in self.event_hashes.items()
                if current_time - ts > self.hash_expiry_seconds
            ]
            for h in expired:
                del self.event_hashes[h]

            if expired:
                logger.debug(f"Cleaned up {len(expired)} expired event hashes")

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
        """분류 결과 파싱 (안전한 파싱)"""
        classified = []
        current_idx = None
        current_category = None
        current_significant = False

        for line in response.strip().split("\n"):
            line = line.strip()

            # Handle formats like "1. INDEX: 1" or "INDEX: 1"
            if "INDEX:" in line:
                # Save previous entry if valid
                if current_idx is not None and current_significant:
                    if 0 <= current_idx < len(events):
                        classified.append((events[current_idx], current_category or "other"))

                # Parse new INDEX safely
                try:
                    idx_part = line.split("INDEX:")[1].strip()
                    # Handle various formats: "0", "0 ", "0,", etc.
                    idx_str = ""
                    for char in idx_part:
                        if char.isdigit():
                            idx_str += char
                        else:
                            break
                    current_idx = int(idx_str) if idx_str else None
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse INDEX from: {line}, error: {e}")
                    current_idx = None

                current_category = None
                current_significant = False

            elif "CATEGORY:" in line:
                try:
                    category_part = line.split("CATEGORY:")[1].strip().lower()
                    # Clean up category (remove extra chars)
                    current_category = category_part.split()[0] if category_part else "other"
                except (IndexError, AttributeError):
                    current_category = "other"

            elif "SIGNIFICANT:" in line:
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
        """트리거 및 감지 레이어 상태 반환"""
        status = {
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
            "detection_layers": {},
        }

        # Anomaly Detector 상태
        if self.anomaly_detector:
            status["detection_layers"]["anomaly_detector"] = self.anomaly_detector.get_status()

        # Semantic Clusterer 상태
        if self.semantic_clusterer:
            status["detection_layers"]["semantic_clusterer"] = {
                "initialized": self._clustering_initialized,
                **self.semantic_clusterer.get_status(),
            }

        return status


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
