"""
에이전트 설정 - 다중 트리거 시스템

트리거 소스:
- GDELT: 뉴스 (무료, 15분 딜레이)
- X/Twitter: 실시간 (Twikit, 개인계정)
- Telegram: 실시간 (Telethon, 가입채널)

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
    # 스캐너 설정
    # ===========================================
    scan_interval_minutes: int = 60  # 프로덕션용 60분 간격
    max_news_per_scan: int = 100

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


agent_settings = AgentSettings()
