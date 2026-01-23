"""
다중 소스 뉴스 스캐너

트리거 소스 (Tier 기반):
- Tier-1 (0.90-0.99): GDELT, GDELT Anomaly, USGS, NOAA
- Tier-2 (0.75-0.85): Currents API, World News API, ACLED
- Tier-3 (0.30-0.40): Reddit, Bluesky, Telegram, Google Trends

특징:
- 멀티소스 교차 검증
- Two-Source Rule (저널리즘 표준)
- 키워드 기반 글로벌 검색
- 결정론적 유의성 점수 + LLM 검증
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .checkworthiness import check_worthiness, RejectionReason
from .config import agent_settings
from .event_verifier import verify_event_hybrid
from .specificity import check_specificity
from .triggers import TriggerEvent, TriggerManager, TriggerSource
from .triggers.base import SourceTier, SOURCE_TIER_MAP
from .significance import (
    calculate_significance,
    filter_significant_events,
    classify_with_llm,
    SignificanceScore,
    SignificanceConfig,
)
from .cross_source_matcher import CrossSourceMatcher, MatchedEvent
from .confidence_scorer import MultiSourceConfidenceScorer, ConfidenceResult, PublishRecommendation

logger = logging.getLogger(__name__)


# ============================================
# 국제 정세 카테고리 키워드 매핑
# ============================================
INTERNATIONAL_AFFAIRS_KEYWORDS = {
    "war": [
        "war", "warfare", "invasion", "invade", "invaded",
        "airstrike", "air strike", "missile", "bombing", "bombed",
        "troops", "offensive", "military operation", "combat",
        "shelling", "artillery", "drone strike",
    ],
    "conflict": [
        "conflict", "clash", "clashes", "fighting",
        "battle", "skirmish", "ceasefire", "cease-fire",
        "hostilities", "armed conflict", "gunfire",
        "border tension", "territorial dispute",
    ],
    "politics": [
        "summit", "sanctions", "election", "elections",
        "president", "prime minister", "parliament",
        "government", "regime", "administration",
        "foreign minister", "state department", "foreign policy",
        "bilateral", "vote", "legislation",
    ],
    "security": [
        "nuclear", "cyberattack", "cyber attack",
        "espionage", "intelligence", "spy", "spying",
        "security threat", "national security",
        "hacking", "breach", "surveillance",
    ],
    "military": [
        "military", "army", "navy", "air force",
        "defense", "defence", "weapons", "deployment",
        "troops", "soldiers", "forces", "base", "bases",
        "warship", "fighter jet", "tank", "submarine",
    ],
    "terrorism": [
        "terrorist", "terrorism", "terror attack",
        "extremist", "hostage", "kidnapping",
        "ISIS", "Al-Qaeda", "Taliban", "militant",
        "suicide bomb", "car bomb", "IED",
    ],
    "diplomacy": [
        "diplomat", "diplomatic", "embassy",
        "treaty", "negotiation", "negotiations",
        "ambassador", "envoy", "bilateral",
        "multilateral", "UN", "United Nations",
        "peace talks", "agreement", "accord",
    ],
}


class MultiSourceScanner:
    """
    다중 소스 스캐너

    Tier-1: GDELT, GDELT Anomaly, USGS, NOAA
    Tier-2: Currents API, World News API, ACLED
    Tier-3: Reddit, Bluesky, Telegram, Google Trends
    """

    def __init__(self, on_event_detected: Callable | None = None):
        """
        Args:
            on_event_detected: 사건 감지 시 콜백 (event_description, category)
        """
        self.on_event_detected = on_event_detected
        self.trigger_manager = self._create_trigger_manager()
        self.last_scan: datetime | None = None

        # Multi-source verification components
        self.cross_source_matcher = CrossSourceMatcher(
            similarity_threshold=agent_settings.cross_source_similarity_threshold,
        )
        self.confidence_scorer = MultiSourceConfidenceScorer(
            min_publish_confidence=agent_settings.min_confidence_score,
        )
        self._matcher_initialized = False

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
        """설정 기반 트리거 매니저 생성 (멀티소스)"""
        # NOTE: LLM API 키를 전달하지 않음 - TriggerManager의 LLM 분류 비활성화
        # 대신 Scanner의 significance scoring + LLM 검증 사용
        manager = TriggerManager(
            openai_api_key=None,  # TriggerManager에서 LLM 분류 비활성화
            llm_model=agent_settings.llm_model,
        )

        # ============================================
        # Tier-1 Sources (0.90-0.99)
        # ============================================

        # GDELT DOC (기본 활성화)
        if agent_settings.gdelt_enabled:
            manager.add_gdelt(timespan=agent_settings.gdelt_timespan)
            logger.info("GDELT DOC trigger added (Tier-1)")

        # GDELT Anomaly Detection
        if agent_settings.gdelt_anomaly_enabled:
            manager.add_gdelt_anomaly(
                timespan="2h",  # GDELT requires minimum ~1h for GKG queries
                goldstein_threshold=agent_settings.gdelt_tone_threshold,
            )
            logger.info("GDELT Anomaly trigger added (Tier-1)")

        # USGS Earthquake API
        if agent_settings.usgs_enabled:
            manager.add_usgs(min_magnitude=agent_settings.usgs_min_magnitude)
            logger.info(f"USGS trigger added (Tier-1, M{agent_settings.usgs_min_magnitude}+)")

        # NOAA Weather Alerts
        if agent_settings.noaa_enabled:
            severity = agent_settings.noaa_severity.split(",") if agent_settings.noaa_severity else None
            manager.add_noaa(severity=severity)
            logger.info("NOAA trigger added (Tier-1)")

        # ============================================
        # Tier-2 Sources (0.75-0.85)
        # ============================================

        # Currents API
        if agent_settings.currents_enabled and agent_settings.currents_api_key:
            manager.add_currents(api_key=agent_settings.currents_api_key)
            logger.info("Currents API trigger added (Tier-2)")

        # World News API
        if agent_settings.worldnews_enabled and agent_settings.worldnews_api_key:
            manager.add_worldnews(api_key=agent_settings.worldnews_api_key)
            logger.info("World News API trigger added (Tier-2)")

        # ACLED Conflict Data
        if agent_settings.acled_enabled and agent_settings.acled_api_key:
            manager.add_acled(
                api_key=agent_settings.acled_api_key,
                email=agent_settings.acled_email,
            )
            logger.info("ACLED trigger added (Tier-2)")

        # ============================================
        # Tier-3 Sources (0.30-0.40)
        # ============================================

        # Reddit
        if agent_settings.reddit_enabled:
            subreddits = agent_settings.reddit_subreddits.split(",") if agent_settings.reddit_subreddits else None
            manager.add_reddit(
                subreddits=subreddits,
                min_score=agent_settings.reddit_min_score,
            )
            logger.info(f"Reddit trigger added (Tier-3, {len(subreddits) if subreddits else 'default'} subreddits)")

        # Bluesky
        if agent_settings.bluesky_enabled:
            manager.add_bluesky(min_likes=agent_settings.bluesky_min_likes)
            logger.info("Bluesky trigger added (Tier-3)")

        # Google Trends
        if agent_settings.google_trends_enabled:
            manager.add_google_trends(geo=agent_settings.google_trends_geo)
            logger.info("Google Trends trigger added (Tier-3)")

        # X/Twitter (설정 시 활성화)
        if agent_settings.twitter_enabled and agent_settings.twitter_username:
            manager.add_twitter(
                username=agent_settings.twitter_username,
                email=agent_settings.twitter_email,
                password=agent_settings.twitter_password,
                cookies_path=agent_settings.twitter_cookies_path,
            )
            logger.info("X/Twitter trigger added (Tier-3)")

        # Telegram (설정 시 활성화)
        if agent_settings.telegram_enabled and agent_settings.telegram_api_id:
            channels = agent_settings.get_telegram_channels()
            manager.add_telegram(
                api_id=agent_settings.telegram_api_id,
                api_hash=agent_settings.telegram_api_hash,
                phone=agent_settings.telegram_phone,
                channels=channels if channels else None,
            )
            logger.info(f"Telegram trigger added (Tier-3, {len(channels) if channels else 'default'} channels)")

        return manager

    async def initialize(self) -> dict[str, bool]:
        """모든 트리거 및 검증 컴포넌트 초기화"""
        results = await self.trigger_manager.initialize_all()

        # CrossSourceMatcher 초기화
        if not self._matcher_initialized:
            self._matcher_initialized = await self.cross_source_matcher.initialize()
            results["cross_source_matcher"] = self._matcher_initialized

        return results

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
        이벤트 분류 및 그룹화 (v4: 멀티소스 교차검증 + Two-Source Rule)

        1. Tier-1 정부 소스 (USGS, NOAA) 분리 - 즉시 발행 가능
        2. CrossSourceMatcher로 유사 이벤트 그룹화
        3. ConfidenceScorer로 신뢰도 계산 + Two-Source Rule 적용
        4. 발행 가능 이벤트에 대해 Content Gates 적용
        5. 최종 significance 점수 계산
        """
        if not events:
            return []

        # ============================================
        # Step 1: Tier-1 정부 소스 분리 (USGS, NOAA는 신뢰도 0.99)
        # ============================================
        tier1_govt_events = []
        other_events = []

        for event in events:
            source_tier = SOURCE_TIER_MAP.get(event.source, SourceTier.TIER2_NEWS)
            if source_tier == SourceTier.TIER1_GOVT:
                tier1_govt_events.append(event)
                logger.info(f"[TIER1-GOVT] {event.source.value}: {event.title[:50]}...")
            else:
                other_events.append(event)

        logger.info(
            f"Source classification: {len(tier1_govt_events)} Tier-1 govt, "
            f"{len(other_events)} other sources"
        )

        # ============================================
        # Step 2: CrossSourceMatcher로 이벤트 그룹화
        # ============================================
        matched_clusters: list[MatchedEvent] = []
        if other_events and self._matcher_initialized:
            matched_clusters = self.cross_source_matcher.match_events(other_events)
            logger.info(f"Cross-source matching: {len(matched_clusters)} clusters found")

        # ============================================
        # Step 3: 각 클러스터에 대해 신뢰도 계산
        # ============================================
        publishable_events: list[dict] = []

        # Tier-1 정부 소스는 즉시 발행 가능 (Two-Source Rule 면제)
        for event in tier1_govt_events:
            confidence = self.confidence_scorer.calculate_confidence([{
                "name": event.source.value,
                "tier": SourceTier.TIER1_GOVT.value,
            }])

            logger.info(
                f"[CONFIDENCE] {event.source.value}: {confidence.score:.2f} "
                f"({confidence.recommendation.value})"
            )

            if confidence.score >= agent_settings.min_confidence_score:
                publishable_events.append({
                    "event": event,
                    "confidence": confidence,
                    "cluster_size": 1,
                    "is_tier1_govt": True,
                })

        # 다른 이벤트는 클러스터 기반 신뢰도 계산
        for cluster in matched_clusters:
            sources = cluster.sources
            confidence = self.confidence_scorer.calculate_confidence(sources)

            logger.info(
                f"[CONFIDENCE] Cluster ({cluster.source_count} sources): "
                f"{confidence.score:.2f} ({confidence.recommendation.value}) "
                f"| Two-Source: {confidence.two_source_satisfied} "
                f"| {cluster.primary_event.title[:40]}..."
            )

            # Two-Source Rule 또는 높은 신뢰도 필요
            if (confidence.two_source_satisfied or
                confidence.score >= agent_settings.min_confidence_score):
                publishable_events.append({
                    "event": cluster.primary_event,
                    "confidence": confidence,
                    "cluster_size": cluster.source_count,
                    "matching_events": cluster.matching_events,
                    "is_tier1_govt": False,
                })

        logger.info(
            f"Confidence filter: {len(publishable_events)} events passed "
            f"(threshold={agent_settings.min_confidence_score})"
        )

        if not publishable_events:
            logger.warning("No events passed confidence threshold")
            return []

        # ============================================
        # Step 3.5: 이벤트 검증 (Gate 0) - 하이브리드 방식
        # ============================================
        if agent_settings.event_verification_enabled:
            verified_events = []
            rejected_count = 0

            for item in publishable_events:
                event = item["event"]

                # Tier-1 정부 소스는 검증 면제 (공식 발표)
                if item["is_tier1_govt"]:
                    verified_events.append(item)
                    continue

                # 이벤트 텍스트 구성
                text = f"{event.title} {event.content[:300]}"

                # 하이브리드 검증 (규칙 + LLM)
                is_event, reason = await verify_event_hybrid(
                    text,
                    llm=self.llm if agent_settings.event_verification_use_llm else None,
                    use_llm=agent_settings.event_verification_use_llm,
                )

                if is_event:
                    verified_events.append(item)
                else:
                    rejected_count += 1
                    if agent_settings.log_gate_rejections:
                        logger.info(
                            f"[GATE0-REJECT] {reason}: {event.title[:50]}..."
                        )

            logger.info(
                f"Event verification (Gate 0): {len(verified_events)}/{len(publishable_events)} passed "
                f"({rejected_count} rejected)"
            )
            publishable_events = verified_events

            if not publishable_events:
                logger.warning("No events passed event verification (Gate 0)")
                return []

        # ============================================
        # Step 4: Content Gates 적용 (Tier-1 govt는 일부 면제)
        # ============================================
        gate_passed = []

        for item in publishable_events:
            event = item["event"]
            text = f"{event.title} {event.content}"

            # Tier-1 정부 소스는 checkworthiness 면제 (공식 발표)
            if not item["is_tier1_govt"]:
                # Gate 1: Check-worthiness
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
                                f"{event.title[:50]}..."
                            )
                        continue

            # Gate 2: Specificity (영어 기사만 적용 - 패턴이 영어 전용)
            # Tier-1 govt 또는 비영어 기사는 스킵
            is_english = getattr(event, 'language', 'en') in ['en', 'english', '']
            if agent_settings.specificity_enabled and is_english and not item["is_tier1_govt"]:
                spec_result = check_specificity(text, min_score=agent_settings.min_specificity_score)
                if not spec_result.is_specific:
                    if agent_settings.log_gate_rejections:
                        logger.info(
                            f"[GATE2-REJECT] Low specificity ({spec_result.score:.2f}): "
                            f"{event.title[:50]}..."
                        )
                    continue

            gate_passed.append(item)

        logger.info(f"Content gates: {len(gate_passed)}/{len(publishable_events)} passed")

        if not gate_passed:
            return []

        # ============================================
        # Step 5: 카테고리별 이벤트 제한 및 다양성 보장
        # ============================================
        max_per_category = agent_settings.max_events_per_category
        category_counts: dict[str, int] = {}  # 카테고리별 카운터
        limited_events = []

        for item in gate_passed:
            event = item["event"]
            category = self._infer_category_from_event(event)

            # 카테고리별 제한 적용
            current_count = category_counts.get(category, 0)
            if current_count >= max_per_category:
                logger.debug(
                    f"[LIMIT] Skipping {category} event (max {max_per_category} reached): "
                    f"{event.title[:40]}..."
                )
                continue

            category_counts[category] = current_count + 1
            item["_category"] = category  # 캐싱
            limited_events.append(item)

        logger.info(
            f"Category limiting: {len(limited_events)}/{len(gate_passed)} events "
            f"(max {max_per_category} per category)"
        )

        # 로그로 카테고리별 분포 출력
        for cat, count in sorted(category_counts.items()):
            logger.info(f"  {cat}: {count} events")

        # ============================================
        # Step 5.5: 국제 정세 카테고리 필터 (선택적)
        # ============================================
        if agent_settings.focus_international_affairs:
            allowed_categories = agent_settings.get_international_affairs_categories()
            filtered_by_category = []
            excluded_counts: dict[str, int] = {}

            for item in limited_events:
                category = item.get("_category", "other")
                if category in allowed_categories:
                    filtered_by_category.append(item)
                else:
                    excluded_counts[category] = excluded_counts.get(category, 0) + 1

            logger.info(
                f"International affairs filter: {len(filtered_by_category)}/{len(limited_events)} events "
                f"(allowed: {', '.join(allowed_categories)})"
            )

            if excluded_counts:
                excluded_str = ", ".join(f"{cat}({cnt})" for cat, cnt in sorted(excluded_counts.items()))
                logger.info(f"  Excluded categories: {excluded_str}")

            limited_events = filtered_by_category

            if not limited_events:
                logger.warning("No events passed international affairs filter")
                return []

        # ============================================
        # Step 6: 다양성을 위한 인터리빙 (뉴스 카테고리 우선)
        # ============================================
        if agent_settings.ensure_category_diversity:
            # 자연재해와 기타 카테고리 분리
            disaster_events = []
            news_events = []

            for item in limited_events:
                category = item.get("_category", "other")
                if category == "natural_disaster":
                    disaster_events.append(item)
                else:
                    news_events.append(item)

            # 뉴스를 먼저, 자연재해를 나중에 (인터리빙)
            # 뉴스 2개당 재해 1개 비율로 섞기
            interleaved = []
            news_idx, disaster_idx = 0, 0

            while news_idx < len(news_events) or disaster_idx < len(disaster_events):
                # 뉴스 2개 추가
                for _ in range(2):
                    if news_idx < len(news_events):
                        interleaved.append(news_events[news_idx])
                        news_idx += 1
                # 자연재해 1개 추가
                if disaster_idx < len(disaster_events):
                    interleaved.append(disaster_events[disaster_idx])
                    disaster_idx += 1

            limited_events = interleaved
            logger.info(
                f"Category diversity: {len(news_events)} news, {len(disaster_events)} disasters "
                f"(interleaved 2:1 ratio)"
            )

        # ============================================
        # Step 7: 최종 결과 포맷팅
        # ============================================
        results = []
        for item in limited_events:
            event = item["event"]
            confidence = item["confidence"]

            # 캐싱된 카테고리 사용 (없으면 추론)
            category = item.get("_category") or self._infer_category_from_event(event)

            # 소스 목록 구성
            sources = [event.source_name]
            if "matching_events" in item:
                sources.extend([e.source_name for e in item["matching_events"]])

            results.append({
                "description": event.title,
                "category": category,
                "sources": sources,
                "source_count": item["cluster_size"],
                "trigger_source": event.source.value,
                "keywords": event.keywords_matched,
                "url": event.url,
                "confidence_score": round(confidence.score, 3),
                "confidence_level": confidence.level.value,
                "two_source_satisfied": confidence.two_source_satisfied,
                "recommendation": confidence.recommendation.value,
                "is_tier1_govt": item["is_tier1_govt"],
            })

            logger.info(
                f"[PUBLISH] {confidence.score:.2f} | {category} | "
                f"{item['cluster_size']} sources | {event.title[:50]}..."
            )

        return results

    def _infer_category_from_event(self, event: TriggerEvent) -> str:
        """TriggerEvent에서 카테고리 추론 (국제 정세 세분화)"""
        text = f"{event.title} {event.content}".lower()

        # 소스 기반 카테고리
        if event.source == TriggerSource.USGS:
            return "natural_disaster"
        if event.source == TriggerSource.NOAA:
            return "natural_disaster"

        # 국제 정세 키워드 매핑 기반 분류 (우선순위 순)
        for category, keywords in INTERNATIONAL_AFFAIRS_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return category

        # 기타 카테고리 (국제 정세 외)
        if any(kw in text for kw in ["earthquake", "tsunami", "flood", "hurricane", "wildfire", "tornado"]):
            return "natural_disaster"
        if any(kw in text for kw in ["protest", "demonstration", "riot", "rally"]):
            return "protest"
        if any(kw in text for kw in ["violence", "killed", "casualties", "shooting"]):
            return "violence"

        return "other"

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

    def _infer_category(self, event_dict: dict, score: SignificanceScore = None) -> str:
        """키워드 기반 카테고리 추론 (dict용)"""
        text = f"{event_dict['title']} {event_dict.get('content', '')}".lower()

        if any(kw in text for kw in ["earthquake", "tsunami", "flood", "hurricane"]):
            return "natural_disaster"
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
        API용 스캔 메서드 (멀티소스)

        Args:
            sources: 스캔할 소스 목록. None이면 활성화된 모든 소스.
                     Tier-1: gdelt, gdelt_anomaly, usgs, noaa
                     Tier-2: currents, worldnews, acled
                     Tier-3: reddit, bluesky, google_trends, twitter, telegram
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
    print("MULTI-SOURCE SCANNER TEST")
    print("=" * 70)
    print("Tier-1: GDELT, GDELT Anomaly, USGS, NOAA")
    print("Tier-2: Currents, WorldNews, ACLED")
    print("Tier-3: Reddit, Bluesky, Google Trends, Twitter, Telegram")
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
