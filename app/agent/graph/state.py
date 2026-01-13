"""
LangGraph state definitions for investigation agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    """Event category."""

    WAR = "war"
    PROTEST = "protest"
    TERRORISM = "terrorism"
    MILITARY = "military"
    VIOLENCE = "violence"
    CIVIL_UNREST = "civil_unrest"
    OTHER = "other"


class SourceType(str, Enum):
    """Source type."""

    NEWS = "news"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    VIDEO = "video"
    IMAGE = "image"


class CollectedItem(BaseModel):
    """Collected item from sources."""

    source_type: SourceType
    source_name: str  # e.g., "Reuters", "@iran_news"
    title: str | None = None
    content: str
    url: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    raw_data: dict = Field(default_factory=dict)


class VerifiedFact(BaseModel):
    """Verified fact with source attribution."""

    claim: str
    supporting_sources: list[str]  # Source names
    confidence: float  # 0.0 - 1.0
    conflicting_info: str | None = None


class InvestigationPlan(BaseModel):
    """Investigation plan."""

    questions: list[str]
    suggested_sources: list[str]
    reasoning: str


class InvestigationReport(BaseModel):
    """Final investigation report."""

    event_summary: str
    category: EventCategory | str
    location: str | None = None
    timeline: list[str]
    verified_facts: list[VerifiedFact | dict]
    media: list[str]  # Media URLs
    sources: list[str]
    unverified_claims: list[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class InvestigationState(TypedDict):
    """LangGraph state for investigation agent."""

    # Input
    event: str  # Triggered event description
    event_category: str  # Category

    # Investigation process
    plan: dict | None  # InvestigationPlan
    collected_items: list[dict]  # CollectedItems
    verified_facts: list[dict]  # VerifiedFacts

    # Metadata
    iteration: int  # Current iteration count
    tool_calls_count: int  # Tool calls counter (to prevent infinite loops)
    messages: list[Any]  # LLM conversation history

    # Output
    report: dict | None  # InvestigationReport
    status: str  # "planning", "collecting", "verifying", "publishing", "done"
