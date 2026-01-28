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
    brave_enabled: bool = True  # P0: Added for consistency with other triggers
    brave_api_key: str = ""

    # ===========================================
    # 트리거 소스 설정
    # ===========================================

    # GDELT (뉴스) - 인증 불필요
    gdelt_enabled: bool = True
    gdelt_timespan: str = "30min"  # 검색 기간 (30분, 15분 스캔에 최적화)


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

    # Social Detection (Tier-3) - DISABLED in Tier-1/2 only mode
    reddit_enabled: bool = False  # Disabled: Tier-3 source excluded
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

    # Recency filter - DISABLED (triggers already validate recency)
    # P0 Optimization: Each trigger (GDELT, Currents, WorldNews) validates recency
    # via validate_trigger_recency, making scanner-level filter redundant
    recency_filter_enabled: bool = False  # Disabled - triggers handle this
    max_event_age_hours: int = 6  # Kept for backward compatibility

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

    # ===========================================
    # 조사 에이전트 설정
    # ===========================================
    max_investigation_iterations: int = 3


    # ===========================================
    # 중복 제거 설정 (Deduplication)
    # ===========================================
    dedup_enabled: bool = True

    # === Layer 1: Title Similarity (Fast, no embedding) ===
    # Uses SequenceMatcher for string similarity
    title_similarity_duplicate: float = 0.85   # >= 85% title match = skip
    title_similarity_potential: float = 0.70   # 70-85% = verify with embedding

    # === Layer 2: Semantic Similarity (Embedding-based) ===
    # Similarity thresholds (tune based on actual data distribution)
    # >= duplicate: Skip as duplicate
    # >= potential: Needs LLM verification
    # >= related: Link as story chain
    # < related: Create new event
    #
    # NOTE: Cross-source embedding similarity typically shows:
    # - Identical titles from different sources: ~84% similarity
    # - Same story, different wording: 60-86% similarity
    # Original thresholds (0.95/0.85/0.70) were too high for cross-source dedup.
    # Lowered based on empirical data analysis (2026-01-27).
    # P2 Fix: Further lowered based on log analysis (2026-01-28):
    # - 70.53% Trump Iran articles were not caught as duplicates
    # - 67.96% TikTok articles were not caught as duplicates
    dedup_duplicate_threshold: float = 0.75    # 확실한 중복 (스킵) - was 0.80
    dedup_potential_threshold: float = 0.65    # 잠재적 일치 (LLM 검증 필요) - was 0.70
    dedup_related_threshold: float = 0.55      # 관련 이벤트 (스토리 체인) - unchanged
    dedup_time_window_days: int = 7            # 조회 기간 (일)

    # === Layer 3: Re-embedding with Canonical Title ===
    # After LLM generates canonical headline, regenerate embedding
    # and re-check for duplicates (catches cross-source duplicates)
    dedup_reembed_canonical: bool = True       # Re-embed with canonical title

    # === Layer 4: Entity Matching ===
    # Check key entity overlap (people, places, organizations)
    entity_overlap_threshold: float = 0.60     # 60% entity overlap = related

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
    # LLM Classifier Settings (Deepinfra)
    # ===========================================
    # Enable/disable LLM-based news classification
    llm_classifier_enabled: bool = True

    # Deepinfra API for cost-effective LLM inference
    # Cost: ~$3-5/month for ~2000 articles/day
    deepinfra_api_key: str = ""
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"
    llm_classifier_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"

    # Classification settings
    llm_classifier_batch_size: int = 20  # Process articles in batches
    llm_classifier_timeout: float = 30.0  # Timeout per batch request

    # Fallback to pattern-based filtering if LLM fails
    llm_classifier_fallback_enabled: bool = True

    # LLM Cost Optimization: Move deduplication BEFORE LLM call
    # This prevents LLM calls for articles that will be deduplicated anyway
    dedup_before_llm: bool = True  # Title dedup before LLM (saves ~25% LLM costs)

    # ===========================================
    # Domain Whitelist (Tier-1/2 Only)
    # ===========================================
    # Enable domain whitelist filtering (reject Tier-3 sources)
    domain_whitelist_enabled: bool = True

    # Disable Tier-3 sources (Reddit, etc.) when whitelist is enabled
    disable_tier3_sources: bool = True

    # ===========================================
    # 콘텐츠 필터링 게이트 설정
    # ===========================================

    # Gate 0: Event Verification (이벤트 검증)
    event_verification_enabled: bool = True   # 이벤트 검증 활성화
    event_verification_use_llm: bool = False  # LLM 검증 비활성화 (규칙만 사용하여 비용 절감)

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

    # ===========================================
    # News Type Classification (Retrospective Filter)
    # ===========================================
    news_classification_enabled: bool = True  # Enable news type classification
    retrospective_min_confidence: float = 0.25  # Min confidence to reject retrospective

    # ===========================================
    # Temporal Classification (Phase 6)
    # ===========================================
    # Enable LLM-based temporal classification
    temporal_classification_enabled: bool = True

    # Auto-reject non-publishable temporal categories (RETROSPECTIVE, PREDICTIVE)
    temporal_filter_enabled: bool = True

    # Temporal categories to reject (comma-separated)
    # Options: retrospective, predictive
    temporal_reject_categories: str = "retrospective,predictive"

    # Log temporal classification results for debugging
    temporal_log_classifications: bool = True

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
