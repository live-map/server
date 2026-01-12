"""
에이전트 설정 - 저렴한 구성

GPT-4o-mini 기반 (입력 $0.15/1M, 출력 $0.60/1M)
"""

from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    # LLM 설정 (저렴한 모델 사용)
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"  # 저렴하고 빠름
    llm_temperature: float = 0.3  # 낮은 온도로 일관성 유지

    # Tavily 검색 (무료 1,000회/월)
    tavily_api_key: str = ""

    # Telegram (기존 설정 활용)
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_phone: str = ""

    # 스캐너 설정
    scan_interval_minutes: int = 15
    max_news_per_scan: int = 50

    # 조사 에이전트 설정
    max_investigation_iterations: int = 3
    min_sources_for_verification: int = 2

    # 비용 제한
    max_tokens_per_investigation: int = 4000  # 비용 제한

    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        extra = "ignore"  # 다른 환경변수 무시


agent_settings = AgentSettings()
