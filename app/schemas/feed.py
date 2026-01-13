"""
Feed schemas matching frontend FeedItem interface.

Reference: client/src/app/security/data/feedData.ts
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class LocationSchema(BaseModel):
    """Geographic location of the event."""

    lat: Optional[float] = Field(None, description="Latitude")
    lng: Optional[float] = Field(None, description="Longitude")
    name: Optional[str] = Field(None, description="Location name")


class FeedItem(BaseModel):
    """
    Feed item schema matching frontend interface.

    Categories:
    - WAR: Active conflict events
    - SECURITY: Security-related events

    SubCategories:
    - ru-uk: Russia-Ukraine
    - is-ir: Israel-Iran
    - US, KOREA, CHINA, JAPAN, etc.
    """

    id: int
    title: str = Field(..., max_length=500)
    content: str
    originalLink: Optional[str] = Field(None, alias="original_link")
    sourceName: str = Field(..., alias="source_name")
    sourceType: str = Field(..., alias="source_type")  # RSS, TELEGRAM, etc.
    publishedAt: datetime = Field(..., alias="published_at")
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    category: Literal["WAR", "SECURITY"]
    subCategory: str = Field(..., alias="sub_category")
    location: LocationSchema

    # Verification fields (added by pipeline)
    credibilityScore: Optional[int] = Field(
        None, alias="credibility_score", ge=0, le=100
    )
    verificationStatus: Optional[str] = Field(None, alias="verification_status")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class FeedResponse(BaseModel):
    """Response wrapper for feed list."""

    items: list[FeedItem]
    total: int
    page: int = 1
    page_size: int = 20
