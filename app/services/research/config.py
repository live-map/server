"""
AI Research Agent configuration.

환경변수에서 AI 관련 설정을 로드합니다.
Multi-model 지원: 노드별 최적 모델 배정.
모든 파이프라인 설정값을 중앙 집중 관리합니다.
"""

from __future__ import annotations

import re

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH_TIMEOUT: int = 300
RESEARCH_STATUS_TTL: int = 86400
MAX_RETRY_COUNT: int = 2
MAX_SOURCES_TO_SAVE: int = 20

# 노드별 타임아웃 (초). None이면 전역 타임아웃에 위임.
NODE_TIMEOUTS: dict[str, int] = {
    "perspective_discovery": 30,
    "planner": 30,
    "web_search": 60,
    "academic_search": 60,
    "fact_check": 30,
    "gap_analyzer": 45,
    "outline_generator": 30,
    "synthesizer": 120,
    "reviewer": 30,
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Search Limits
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TAVILY_MAX_RESULTS: int = 5
DUCKDUCKGO_MAX_RESULTS: int = 5
DUCKDUCKGO_DELAY: float = 0.5
ACADEMIC_MAX_RESULTS: int = 3
ACADEMIC_DELAY: float = 1.0
FACT_CHECK_MAX_RESULTS: int = 3

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Content Filtering
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MIN_SNIPPET_LENGTH: int = 50
JINA_ENRICH_THRESHOLD: int = 200
JINA_MAX_CHARS: int = 1500
MAX_SNIPPET_LENGTH: int = 1500
JINA_ENRICH_LIMIT: int = 20
WEB_SOURCE_LIMIT: int = 15
WEB_SNIPPET_MAX: int = 800
ACADEMIC_SOURCE_LIMIT: int = 10
ACADEMIC_SNIPPET_MAX: int = 600
FACT_CHECK_DISPLAY_LIMIT: int = 10
GAP_ANALYSIS_SOURCE_LIMIT: int = 15
GAP_FOLLOWUP_QUERIES: int = 3
GAP_FOLLOWUP_RESULTS: int = 3

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Credibility Thresholds
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREDIBILITY_HIGH_THRESHOLD: float = 0.7
CREDIBILITY_MEDIUM_THRESHOLD: float = 0.4
CONFIDENCE_HIGH_MIN_SOURCES: int = 10
CONFIDENCE_HIGH_MIN_CREDIBILITY: float = 2.5
CONFIDENCE_MEDIUM_MIN_SOURCES: int = 5
CONFIDENCE_MEDIUM_MIN_CREDIBILITY: float = 1.5

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. LLM Parameters (node overrides)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFAULT_MAX_TOKENS: int = 1024
DEFAULT_TEMPERATURE: float = 0.3
SYNTHESIZER_MAX_TOKENS: int = 4096
SYNTHESIZER_TEMPERATURE: float = 0.4
SYNTHESIZER_REVISION_TEMPERATURE: float = 0.2
OUTLINE_MAX_TOKENS: int = 2048
OUTLINE_TEMPERATURE: float = 0.4
REVIEWER_TEMPERATURE: float = 0.2
REVIEWER_PASS_SCORE: int = 60
REVIEWER_DEFAULT_SCORE: int = 80
REVIEWER_MIN_VISUAL_ELEMENTS: int = 2
OUTLINE_MAPPING_THRESHOLD: float = 0.5
FALLBACK_PERSPECTIVES_LIMIT: int = 4
PLANNER_WEB_QUERY_LIMIT: int = 8
PLANNER_ACADEMIC_QUERY_LIMIT: int = 4
PLANNER_FACTCHECK_CLAIM_LIMIT: int = 4

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. HTTP Timeouts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JINA_TIMEOUT: float = 10.0
FACT_CHECK_TIMEOUT: float = 10.0
SEMANTIC_SCHOLAR_TIMEOUT: float = 15.0
UNSPLASH_TIMEOUT: float = 10.0
TAVILY_RAW_CONTENT_MAX: int = 2000
TAVILY_CONTENT_MAX: int = 800

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. Domain Lists (통합 — 중복 제거)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCKED_DOMAINS: set[str] = {
    "wiktionary.org", "merriam-webster.com", "dictionary.com", "thesaurus.com",
    "namu.wiki", "ko.wikipedia.org", "en.wikipedia.org", "wikipedia.org",
    "blog.naver.com", "m.blog.naver.com", "tistory.com", "brunch.co.kr",
    "medium.com", "velog.io", "notion.so",
    "reddit.com", "quora.com", "dcinside.com", "fmkorea.com", "theqoo.net",
    "clien.net", "ruliweb.com", "ppomppu.co.kr",
    "maxpreps.com", "espn.com", "sports.yahoo.com",
    "imdb.com", "rottentomatoes.com",
    "amazon.com", "ebay.com", "coupang.com",
    "youtube.com",
}

BLOCKED_URL_PATTERNS: re.Pattern = re.compile(
    r"(blog\.|/blog/|tistory\.com|brunch\.co\.kr|velog\.io|/PostView|"
    r"namu\.wiki|wikipedia\.org|reddit\.com|youtube\.com)",
    re.IGNORECASE,
)

TRUSTED_DOMAINS: set[str] = {
    "korea.kr", "molit.go.kr", "fsc.go.kr", "law.go.kr",
    "nec.go.kr", "kostat.go.kr", "bok.or.kr",
    "yna.co.kr", "yonhapnews.co.kr",
    "news.kbs.co.kr", "imnews.imbc.com", "news.sbs.co.kr",
    "chosun.com", "joongang.co.kr", "donga.com",
    "hani.co.kr", "khan.co.kr", "mk.co.kr", "hankyung.com",
    "koreaherald.com", "koreatimes.co.kr",
    "kdi.re.kr", "kiep.go.kr", "krei.re.kr", "keei.re.kr",
    "bbc.com", "reuters.com", "apnews.com", "nytimes.com",
    "theguardian.com", "economist.com",
}

KOREAN_TRUSTED_DOMAINS: list[str] = [
    "bbc.com/korean",
    "yonhapnews.co.kr", "hani.co.kr", "khan.co.kr",
    "chosun.com", "donga.com", "joongang.co.kr",
    "mk.co.kr", "mt.co.kr", "hankyung.com", "sedaily.com",
    "yna.co.kr", "kbs.co.kr", "sbs.co.kr", "mbc.co.kr",
    "bok.or.kr", "kostat.go.kr", "kdi.re.kr", "nars.go.kr",
]

TAVILY_EXCLUDE_DOMAINS: list[str] = [
    "namu.wiki", "wikipedia.org", "ko.wikipedia.org", "en.wikipedia.org",
    "blog.naver.com", "m.blog.naver.com", "tistory.com", "brunch.co.kr",
    "medium.com", "velog.io", "reddit.com", "youtube.com", "quora.com",
    "dcinside.com", "fmkorea.com", "theqoo.net", "clien.net",
    "ruliweb.com", "ppomppu.co.kr", "notion.so",
]

REVIEWER_BLOCKED_DOMAINS: list[str] = [
    "namu.wiki", "blog.naver.com", "tistory.com",
    "wikipedia.org", "medium.com", "velog.io", "brunch.co.kr",
]

NEWS_DOMAINS: set[str] = {
    "yonhapnews.co.kr", "yna.co.kr", "hani.co.kr", "khan.co.kr",
    "chosun.com", "donga.com", "joongang.co.kr", "mk.co.kr",
    "mt.co.kr", "hankyung.com", "sedaily.com", "kbs.co.kr",
    "sbs.co.kr", "mbc.co.kr", "bbc.com", "reuters.com",
    "apnews.com", "nytimes.com", "washingtonpost.com",
}

GOV_DOMAINS: set[str] = {
    "go.kr", "gov.kr", "bok.or.kr", "kostat.go.kr",
    "nars.go.kr", "kdi.re.kr",
}

ACADEMIC_DOMAINS: set[str] = {
    "scholar.google.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov",
    "semanticscholar.org", "jstor.org", "nature.com", "science.org",
}


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
