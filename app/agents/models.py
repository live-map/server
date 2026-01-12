"""
에이전트 상태 모델 (LangGraph용)
"""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    """이벤트 카테고리"""

    WAR = "war"
    PROTEST = "protest"
    TERRORISM = "terrorism"
    MILITARY = "military"
    VIOLENCE = "violence"
    CIVIL_UNREST = "civil_unrest"
    OTHER = "other"


class SourceType(str, Enum):
    """소스 유형"""

    NEWS = "news"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    RSS = "rss"
    VIDEO = "video"
    IMAGE = "image"


class CollectedItem(BaseModel):
    """수집된 아이템"""

    source_type: SourceType
    source_name: str  # e.g., "Reuters", "@iran_news"
    title: str | None = None
    content: str
    url: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    raw_data: dict = Field(default_factory=dict)


class VerifiedFact(BaseModel):
    """검증된 사실"""

    claim: str
    supporting_sources: list[str]  # 소스 이름들
    confidence: float  # 0.0 - 1.0
    conflicting_info: str | None = None


class InvestigationPlan(BaseModel):
    """조사 계획"""

    questions: list[str]
    suggested_sources: list[str]
    reasoning: str


class InvestigationReport(BaseModel):
    """최종 리포트"""

    event_summary: str
    category: EventCategory
    location: str | None = None
    timeline: list[str]
    verified_facts: list[VerifiedFact]
    media: list[str]  # 미디어 URLs
    sources: list[str]
    unverified_claims: list[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# LangGraph State
class InvestigationState(TypedDict):
    """LangGraph 상태"""

    # 입력
    event: str  # 트리거된 사건 설명
    event_category: str  # 카테고리

    # 조사 과정
    plan: dict | None  # InvestigationPlan
    collected_items: list[dict]  # CollectedItem들
    verified_facts: list[dict]  # VerifiedFact들

    # 메타데이터
    iteration: int  # 현재 반복 횟수
    messages: list[Any]  # LLM 대화 히스토리

    # 출력
    report: dict | None  # InvestigationReport
    status: str  # "planning", "collecting", "verifying", "publishing", "done"
