"""
에이전트 설정 - 다중 트리거 시스템

트리거 소스:
- GDELT: 뉴스 (무료, 15분 딜레이)
- X/Twitter: 실시간 (Twikit, 개인계정)
- Telegram: 실시간 (Telethon, 가입채널)

LLM:
- GPT-4o-mini 기반 (입력 $0.15/1M, 출력 $0.60/1M)
"""

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
    gdelt_timespan: str = "1h"  # 검색 기간

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
    scan_interval_minutes: int = 15
    max_news_per_scan: int = 50

    # ===========================================
    # 조사 에이전트 설정
    # ===========================================
    max_investigation_iterations: int = 3
    min_sources_for_verification: int = 2
    max_tokens_per_investigation: int = 4000

    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        extra = "ignore"

    def get_telegram_channels(self) -> list[str]:
        """텔레그램 채널 목록 파싱"""
        if not self.telegram_channels:
            return []
        return [ch.strip() for ch in self.telegram_channels.split(",") if ch.strip()]


agent_settings = AgentSettings()
