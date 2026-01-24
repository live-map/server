"""
에이전트 설정 - 멀티소스 트리거 시스템

트리거 소스 (Tier 기반):
- Tier-1 (0.90-0.99): GDELT, USGS, NOAA, EMSC
- Tier-2 (0.75-0.85): Currents API, World News API, ACLED
- Tier-3 (0.30-0.40): Reddit, Bluesky, Telegram, Google Trends

LLM:
- GPT-4o-mini 기반 (입력 $0.15/1M, 출력 $0.60/1M)
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    # ===========================================
    # LLM 설정
    # ===========================================
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3

    # Tavily 검색 (무료 1,000회/월)
    tavily_api_key: str = ""

    # P1: Brave Search (무료 2,000회/월)
    brave_api_key: str = ""

    # ===========================================
    # 트리거 소스 설정
    # ===========================================

    # GDELT (뉴스) - 인증 불필요
    gdelt_enabled: bool = True
    gdelt_timespan: str = "2h"  # 검색 기간 (2시간, 프로덕션용)


    # X/Twitter (Twikit) - 개인계정 필요
    twitter_enabled: bool = False
    twitter_username: str = ""
    twitter_email: str = ""
    twitter_password: str = ""
    twitter_cookies_path: str = "twitter_cookies.json"

    # Telegram (Telethon) - API 인증 필요
    telegram_enabled: bool = False
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    telegram_session_path: str = "telegram_session"
    telegram_channels: str = ""  # 콤마 구분 채널 목록

    # ===========================================
    # 멀티소스 트리거 설정 (Phase 1-4)
    # ===========================================

    # GDELT Anomaly Detection
    gdelt_anomaly_enabled: bool = True
    gdelt_use_gkg_themes: bool = True
    gdelt_tone_threshold: float = -5.0  # Goldstein proxy

    # Social Detection (Tier-3)
    reddit_enabled: bool = True
    reddit_subreddits: str = "worldnews,news,UkrainianConflict,geopolitics"
    reddit_min_score: int = 50

    bluesky_enabled: bool = False  # 403 인증 필요 - 비활성화
    bluesky_min_likes: int = 10

    google_trends_enabled: bool = False  # 429 rate limit 심함 - 비활성화
    google_trends_geo: str = "US"

    # News APIs (Tier-2) - P1: Enabled by default (requires API keys)
    currents_enabled: bool = True  # P1: Enable if API key provided
    currents_api_key: str = ""

    worldnews_enabled: bool = True  # P1: Enable if API key provided
    worldnews_api_key: str = ""

    # Specialized APIs (Tier-1/2)
    # 국제 정세 집중 전략: 자연재해 소스 비활성화
    usgs_enabled: bool = False  # 지진 비활성화 (USGS 공식 채널 존재)
    usgs_min_magnitude: float = 5.0

    noaa_enabled: bool = False  # 날씨 비활성화 (NOAA 공식 채널 존재)
    noaa_severity: str = "Extreme,Severe"

    acled_enabled: bool = False
    acled_api_key: str = ""
    acled_email: str = ""

    # ===========================================
    # 멀티소스 신뢰도 설정
    # ===========================================
    min_confidence_score: float = 0.70  # 발행 최소 신뢰도
    cross_source_similarity_threshold: float = 0.70  # 소스간 매칭 임계값

    # ===========================================
    # 스캐너 설정
    # ===========================================
    scan_interval_minutes: int = 15  # 멀티소스용 15분 간격
    max_news_per_scan: int = 100

    # Recency filter - reject articles older than this threshold
    max_event_age_hours: int = 48  # Maximum age for events to be processed

    # 카테고리별 이벤트 제한 (큐 다양성 보장)
    max_events_per_category: int = 5  # 각 카테고리당 최대 이벤트 수
    ensure_category_diversity: bool = True  # 다양한 카테고리 우선

    # ===========================================
    # 국제 정세 집중 전략
    # ===========================================
    focus_international_affairs: bool = True  # 국제 정세 카테고리만 처리
    international_affairs_categories: str = "war,conflict,politics,security,military,terrorism,diplomacy,protest"

    # ===========================================
    # 유의성 점수 설정 (Significance Scoring)
    # ===========================================
    # 점수 임계값 (0-100)
    # 30: 중간 키워드 1개 + 일반 소스 + 영어 + 기본
    # 40: 중간 키워드 2개 또는 높은 키워드 1개
    # 60: 높은 키워드 여러 개 또는 신뢰 소스
    min_publish_score: int = 40  # 발행 최소 점수 (프로덕션: 품질 우선)

    min_investigate_score: int = 50  # 조사 시작 최소 점수

    # 점수 계산 방식
    use_deterministic_scoring: bool = True  # 결정론적 점수 사용
    use_llm_scoring: bool = True  # LLM 점수도 사용
    combine_scores: bool = True  # 두 점수 조합 (평균)

    # 디버깅
    log_all_scores: bool = True  # 모든 점수 계산 로깅

    # ===========================================
    # 조사 에이전트 설정
    # ===========================================
    max_investigation_iterations: int = 3
    min_sources_for_verification: int = 2
    max_tokens_per_investigation: int = 4000

    # ===========================================

    evidence_gate_enabled: bool = True  # 증거 검증 게이트 활성화
    min_supported_claims: int = 2       # SUPPORTED 판정 필요 최소 주장 수
    min_evidence_ratio: float = 0.5     # 최소 증거 비율 (supported/total)


    # ===========================================
    # 중복 제거 설정 (Deduplication)
    # ===========================================
    dedup_enabled: bool = True
    # Similarity thresholds (tune based on actual data distribution)
    # >= duplicate: Skip as duplicate
    # >= potential: Needs LLM verification
    # >= related: Link as story chain
    # < related: Create new event
    dedup_duplicate_threshold: float = 0.95    # 확실한 중복 (스킵)
    dedup_potential_threshold: float = 0.85    # 잠재적 일치 (LLM 검증 필요)
    dedup_related_threshold: float = 0.70      # 관련 이벤트 (스토리 체인)
    dedup_time_window_days: int = 7            # 조회 기간 (일)
    # Logging for threshold tuning
    dedup_log_all_similarities: bool = True    # 모든 유사도 점수 로깅

    # ===========================================
    # 이중 언어 설정 (Bilingual)
    # ===========================================
    generate_korean: bool = True
    korean_style: str = "formal"  # 합니다체 (formal) or 해요체 (informal)

    # ===========================================
    # LLM 타임아웃 및 동시성 설정
    # ===========================================
    llm_timeout_seconds: float = 60.0
    max_concurrent_llm_calls: int = 3
    investigation_timeout_seconds: float = 300.0  # 5 minutes

    # ===========================================
    # 콘텐츠 필터링 게이트 설정
    # ===========================================

    # Gate 0: Event Verification (이벤트 검증)
    event_verification_enabled: bool = True   # 이벤트 검증 활성화
    event_verification_use_llm: bool = False  # LLM 검증 비활성화 (규칙만 사용하여 비용 절감)
    event_verification_use_zero_shot: bool = False  # Zero-shot 분류 사용 (transformers 필요)
    zero_shot_high_confidence: float = 0.8    # 이 이상이면 바로 결정
    zero_shot_model: str = "facebook/bart-large-mnli"  # Zero-shot 모델

    # Gate 1: Check-worthiness
    checkworthiness_enabled: bool = True
    entertainment_pattern_threshold: int = 2  # N개 이상 패턴 매칭 시 거부
    speculation_pattern_threshold: int = 2
    human_interest_pattern_threshold: int = 3  # 인물 특집/미담 기사 거부

    # Gate 2: Specificity (TODO: 다국어 패턴 추가 필요)
    specificity_enabled: bool = True   # Specificity Gate 활성화
    min_specificity_score: float = 0.4  # 0-1, 이 점수 미만이면 거부

    # Gate 3: Evidence Sufficiency
    evidence_gate_enabled: bool = True
    min_supported_claims: int = 1       # 최소 검증된 주장 수
    min_evidence_ratio: float = 0.3     # 검증된 주장 비율 (0-1)

    # 로깅
    log_gate_rejections: bool = True    # 거부 사유 로깅

    # Pydantic v2 configuration
    model_config = ConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        extra="ignore",
    )

    def get_telegram_channels(self) -> list[str]:
        """텔레그램 채널 목록 파싱"""
        if not self.telegram_channels:
            return []
        return [ch.strip() for ch in self.telegram_channels.split(",") if ch.strip()]

    def get_international_affairs_categories(self) -> list[str]:
        """국제 정세 카테고리 목록 파싱"""
        if not self.international_affairs_categories:
            return ["war", "conflict", "politics", "security", "military", "terrorism", "diplomacy", "protest"]
        return [cat.strip() for cat in self.international_affairs_categories.split(",") if cat.strip()]


agent_settings = AgentSettings()
