"""
Article schemas for API request/response validation.

Includes:
- RelatedSourceSchema: Structured source for "Related Sources" section
- ArticleResponse: Full article response with bilingual content
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RelatedSourceSchema(BaseModel):
    """
    Structured related source for "Related Sources" section.

    Legal compliance:
    - Always includes original URL for traffic attribution
    - Short snippet (1-2 sentences) that doesn't replace original
    - Credibility tier for transparency
    """

    url: str = Field(..., description="Original article URL")
    title: str = Field(..., description="Article title/headline")
    source_name: str = Field(..., description="Source organization name")
    snippet: str = Field("", description="1-2 sentence factual summary")
    credibility_tier: str = Field(
        "tier3",
        description="Source credibility tier (tier1: wire services/gov, tier2: major news, tier3: other)",
    )


class ArticleResponse(BaseModel):
    """
    Full article response schema.

    Includes bilingual content (EN/KO) and related sources.
    """

    id: int
    event_id: int

    # English content
    headline_en: str
    lead_en: str
    nut_graph_en: Optional[str] = None
    body_en: str
    full_text_en: str

    # Korean content
    headline_ko: str
    lead_ko: str
    nut_graph_ko: Optional[str] = None
    body_ko: str
    full_text_ko: str

    # Related sources (for "더 읽을거리" section)
    related_sources: list[RelatedSourceSchema] = Field(
        default_factory=list,
        description="Structured sources for Related Sources section",
    )

    # Verification metadata
    claims_total: int = 0
    claims_verified: int = 0
    claims_refuted: int = 0
    claims_unverifiable: int = 0
    verification_score: float = 0.0

    # Source tracking
    source_count: int = 0

    # Status
    status: str
    is_ai_generated: bool = True
    is_human_reviewed: bool = False
    is_corrected: bool = False
    correction_note: Optional[str] = None

    # Timestamps
    published_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ArticleListItem(BaseModel):
    """Simplified article for list views."""

    id: int
    event_id: int
    headline_en: str
    headline_ko: str
    lead_en: str
    lead_ko: str
    verification_score: float = 0.0
    source_count: int = 0
    status: str
    published_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ArticleListResponse(BaseModel):
    """Response wrapper for article list."""

    items: list[ArticleListItem]
    total: int
    page: int = 1
    page_size: int = 20
