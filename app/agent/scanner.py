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
- 결정론적 유의성 점수 + LLM 검증 (v2)
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .checkworthiness import check_worthiness, RejectionReason
from .config import agent_settings
from .specificity import check_specificity
from .triggers import TriggerEvent, TriggerManager
from .significance import (
    calculate_significance,
    filter_significant_events,
    classify_with_llm,
    SignificanceScore,
    SignificanceConfig,
)

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
        # NOTE: LLM API 키를 전달하지 않음 - TriggerManager의 LLM 분류 비활성화
        # 대신 Scanner의 significance scoring + LLM 검증 사용
        manager = TriggerManager(
            openai_api_key=None,  # TriggerManager에서 LLM 분류 비활성화
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
        """
        이벤트 분류 및 그룹화 (v3: 필터링 게이트 + 결정론적 점수 + LLM)

        1. Gate 1: Check-worthiness (연예/추측 콘텐츠 거부)
        2. Gate 2: Specificity (일반 배경 기사 거부)
        3. 결정론적 점수 계산 (노이즈 필터링)
        4. 선택적 LLM 검증 (높은 점수만)
        5. 모든 결정 로깅
        """
        if not events:
            return []

        # 이벤트를 dict로 변환
        event_dicts = [
            {
                "title": e.title,
                "content": e.content,
                "source_name": e.source_name,
                "source": e.source.value,
                "url": e.url,
                "keywords_matched": e.keywords_matched,
                "language": e.language,
            }
            for e in events
        ]

        # Gate-filtered events
        gate_passed_events = []
        gate_passed_triggers = []

        for event_dict, trigger_event in zip(event_dicts, events):
            text = f"{event_dict['title']} {event_dict.get('content', '')}"

            # === GATE 1: Check-worthiness ===
            if agent_settings.checkworthiness_enabled:
                cw_result = check_worthiness(
                    text,
                    entertainment_threshold=agent_settings.entertainment_pattern_threshold,
                    speculation_threshold=agent_settings.speculation_pattern_threshold,
                    human_interest_threshold=agent_settings.human_interest_pattern_threshold,
                )
                if not cw_result.is_checkworthy:
                    if agent_settings.log_gate_rejections:
                        logger.info(
                            f"[GATE1-REJECT] {cw_result.rejection_reason.value}: "
                            f"{event_dict['title'][:50]}..."
                        )
                    continue

            # === GATE 2: Specificity ===
            if agent_settings.specificity_enabled:
                spec_result = check_specificity(
                    text,
                    min_score=agent_settings.min_specificity_score,
                )
                if not spec_result.is_specific:
                    if agent_settings.log_gate_rejections:
                        logger.info(
                            f"[GATE2-REJECT] Low specificity ({spec_result.score:.2f}): "
                            f"{event_dict['title'][:50]}..."
                        )
                    continue

            gate_passed_events.append(event_dict)
            gate_passed_triggers.append(trigger_event)

        logger.info(
            f"Content gates: {len(gate_passed_events)}/{len(events)} events passed"
        )

        if not gate_passed_events:
            return []

        # 1. 결정론적 점수 계산
        scored_events = []
        for event_dict, trigger_event in zip(gate_passed_events, gate_passed_triggers):
            # GDELT API pre-filters by keyword, so non-English articles
            # that passed GDELT's filter should get base score
            is_api_prefiltered = event_dict["source"] == "gdelt"

            score = calculate_significance(
                title=event_dict["title"],
                content=event_dict.get("content", ""),
                source_domain=event_dict["source_name"],
                language=event_dict.get("language", "en"),
                api_prefiltered=is_api_prefiltered,
            )

            # 로깅 (설정에 따라)
            if agent_settings.log_all_scores:
                logger.info(
                    f"[SCORE] {score.total_score:3d} [{score.level.value:8s}] "
                    f"{event_dict['title'][:60]}... "
                    f"| {score.reasoning}"
                )

            scored_events.append((event_dict, score, trigger_event))

        # 2. 임계값 필터링
        min_score = agent_settings.min_publish_score
        filtered = [
            (e, s, t) for e, s, t in scored_events
            if s.total_score >= min_score
        ]

        logger.info(
            f"Significance filter: {len(filtered)}/{len(scored_events)} events "
            f"passed (threshold={min_score})"
        )

        if not filtered:
            # 모든 이벤트가 필터링됨 - 상세 로그
            logger.warning(
                f"All {len(events)} events filtered out. "
                f"Highest score: {max(s.total_score for _, s, _ in scored_events) if scored_events else 0}"
            )
            return []

        # 2.5. Specificity Gate (구체성 필터)
        if agent_settings.specificity_enabled:
            specificity_passed = []
            for e, s, t in filtered:
                text = f"{e['title']} {e.get('content', '')}"
                spec_result = check_specificity(text, agent_settings.min_specificity_score)

                if spec_result.is_specific:
                    specificity_passed.append((e, s, t))
                else:
                    logger.info(
                        f"[SPECIFICITY REJECTED] score={spec_result.score:.2f} "
                        f"| date={spec_result.has_recent_date} "
                        f"| location={spec_result.has_specific_location} "
                        f"| numbers={spec_result.has_specific_numbers} "
                        f"| {e['title'][:50]}..."
                    )

            logger.info(
                f"Specificity filter: {len(specificity_passed)}/{len(filtered)} events "
                f"passed (min_score={agent_settings.min_specificity_score})"
            )
            filtered = specificity_passed

            if not filtered:
                logger.warning("All events filtered out by specificity gate")
                return []

        # 3. LLM 검증 (선택적)
        if agent_settings.use_llm_scoring and self.llm:
            return await self._llm_validate_and_format(filtered)

        # LLM 없으면 결정론적 결과만 반환
        return self._format_results(filtered)

    async def _llm_validate_and_format(
        self,
        filtered_events: list[tuple[dict, SignificanceScore, TriggerEvent]],
    ) -> list[dict]:
        """LLM으로 추가 검증 및 포맷팅"""
        event_dicts = [e for e, _, _ in filtered_events]

        try:
            llm_results = await classify_with_llm(
                events=event_dicts,
                llm=self.llm,
                min_score=agent_settings.min_publish_score,
            )

            if not llm_results:
                logger.warning("LLM returned no results, using deterministic scores")
                return self._format_results(filtered_events)

            # LLM 결과와 결정론적 점수 조합
            results = []
            for event_dict, llm_score, category, reasoning in llm_results:
                # 원본 이벤트 찾기
                det_score = None
                for e, s, t in filtered_events:
                    if e["title"] == event_dict["title"]:
                        det_score = s
                        break

                # 조합 점수 계산
                if agent_settings.combine_scores and det_score:
                    final_score = (det_score.total_score + llm_score) // 2
                else:
                    final_score = llm_score

                logger.info(
                    f"[FINAL] {final_score:3d} [{category:8s}] "
                    f"{event_dict['title'][:50]}... "
                    f"(det={det_score.total_score if det_score else 'N/A'}, llm={llm_score}) "
                    f"| {reasoning[:50]}"
                )

                results.append({
                    "description": event_dict["title"],
                    "category": category,
                    "sources": [event_dict["source_name"]],
                    "trigger_source": event_dict["source"],
                    "keywords": event_dict.get("keywords_matched", []),
                    "url": event_dict.get("url", ""),
                    "significance_score": final_score,
                    "deterministic_score": det_score.total_score if det_score else None,
                    "llm_score": llm_score,
                    "reasoning": reasoning,
                })

            return results

        except Exception as e:
            logger.error(f"LLM validation error: {e}")
            return self._format_results(filtered_events)

    def _format_results(
        self,
        filtered_events: list[tuple[dict, SignificanceScore, TriggerEvent]],
    ) -> list[dict]:
        """결과 포맷팅 (LLM 없이)"""
        results = []
        for event_dict, score, trigger_event in filtered_events:
            # 카테고리 추론
            category = self._infer_category(event_dict, score)

            results.append({
                "description": event_dict["title"],
                "category": category,
                "sources": [event_dict["source_name"]],
                "trigger_source": event_dict["source"],
                "keywords": event_dict.get("keywords_matched", []),
                "url": event_dict.get("url", ""),
                "significance_score": score.total_score,
                "deterministic_score": score.total_score,
                "reasoning": score.reasoning,
            })

        return results

    def _infer_category(self, event_dict: dict, score: SignificanceScore) -> str:
        """키워드 기반 카테고리 추론"""
        text = f"{event_dict['title']} {event_dict.get('content', '')}".lower()

        if any(kw in text for kw in ["war", "invasion", "airstrike", "troops"]):
            return "war"
        if any(kw in text for kw in ["terrorist", "bombing", "hostage"]):
            return "terrorism"
        if any(kw in text for kw in ["protest", "demonstration", "riot"]):
            return "protest"
        if any(kw in text for kw in ["military", "army", "navy", "air force"]):
            return "military"
        if any(kw in text for kw in ["violence", "killed", "casualties"]):
            return "violence"
        return "other"

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

    async def scan_all_sources(
        self,
        sources: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> list[dict]:
        """
        API용 스캔 메서드

        Args:
            sources: 스캔할 소스 목록 (gdelt, twitter, telegram). None이면 활성화된 모든 소스.
            keywords: 필터링할 키워드. None이면 모든 이벤트.

        Returns:
            감지된 이벤트 목록
        """
        logger.info(f"Scanning sources: {sources or 'all'}, keywords: {keywords}")

        # 트리거 초기화 (아직 안 됐으면)
        await self.trigger_manager.initialize_all()

        # 트리거 매니저에서 특정 소스만 스캔
        events = await self.trigger_manager.scan_all(sources=sources)

        if not events:
            return []

        # 키워드 필터링
        if keywords:
            filtered_events = []
            for event in events:
                event_text = f"{event.title} {event.content}".lower()
                if any(kw.lower() in event_text for kw in keywords):
                    filtered_events.append(event)
            events = filtered_events

        # LLM 분류 (기존 로직 활용)
        significant_events = await self._classify_and_group(events)

        return significant_events


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
