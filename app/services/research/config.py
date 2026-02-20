"""
AI Research Agent configuration.

환경변수에서 AI 관련 설정을 로드합니다.
Multi-model 지원: 노드별 최적 모델 배정.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """AI Research Agent settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    SEMANTIC_SCHOLAR_API_KEY: str = ""
    GOOGLE_FACT_CHECK_API_KEY: str = ""
    UNSPLASH_ACCESS_KEY: str = ""

    # 기본 모델
    AI_MODEL: str = "claude-sonnet-4-5-20250929"
    AI_PROVIDER: str = ""  # "anthropic" | "openai" — auto-detected if empty

    # 노드별 모델 (role-based)
    AI_MODEL_PLANNER: str = "gpt-4o-mini"
    AI_MODEL_SYNTHESIZER: str = "gpt-4o"
    AI_MODEL_REVIEWER: str = "gpt-4o"

    @property
    def provider(self) -> str:
        """Resolve the LLM provider. Auto-detect from available keys."""
        if self.AI_PROVIDER:
            return self.AI_PROVIDER
        if self.ANTHROPIC_API_KEY:
            return "anthropic"
        if self.OPENAI_API_KEY:
            return "openai"
        return ""

    @property
    def research_enabled(self) -> bool:
        """Check if minimum required API keys are configured."""
        has_llm = bool(self.ANTHROPIC_API_KEY or self.OPENAI_API_KEY)
        return has_llm  # Tavily 키 없어도 DuckDuckGo fallback 가능

    def _resolve_model(self, role: str) -> str:
        """역할에 맞는 모델명을 반환합니다."""
        role_map = {
            "planner": self.AI_MODEL_PLANNER,
            "synthesizer": self.AI_MODEL_SYNTHESIZER,
            "reviewer": self.AI_MODEL_REVIEWER,
        }
        return role_map.get(role, self.AI_MODEL)

    def _detect_provider(self, model: str) -> str:
        """모델명에서 provider를 자동 감지합니다."""
        if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
            return "openai"
        if model.startswith("claude"):
            return "anthropic"
        # fallback: 환경 provider
        return self.provider

    def get_chat_model(
        self,
        *,
        role: str = "default",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> BaseChatModel:
        """LLM 인스턴스를 생성합니다. role에 따라 최적 모델 자동 선택."""
        model = self._resolve_model(role)
        p = self._detect_provider(model)

        if p == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                api_key=self.OPENAI_API_KEY,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        else:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model,
                api_key=self.ANTHROPIC_API_KEY,
                max_tokens=max_tokens,
                temperature=temperature,
            )



ai_settings = AISettings()
