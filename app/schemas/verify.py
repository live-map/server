"""
Verification request/response schemas.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    """Request to verify news content."""

    text: str = Field(..., min_length=10, max_length=5000, description="Text content to verify")
    source_name: Optional[str] = Field(None, description="Source name (e.g., 'Telegram Channel')")
    source_type: Optional[str] = Field(None, description="Source type (RSS, TELEGRAM, API)")
    skip_stage3: bool = Field(False, description="Skip LLM stage (for testing/cost saving)")


class LocationInfo(BaseModel):
    """Extracted location information."""

    text: str
    label: str  # GPE or LOC


class VerifyResponse(BaseModel):
    """Response from verification pipeline."""

    # Status
    status: Literal["verified", "partially_verified", "unverified", "false", "skipped"]
    credibility_score: int = Field(..., ge=0, le=100)

    # Location
    locations: list[LocationInfo] = []
    has_location: bool = False

    # Pipeline info
    stages_completed: int = Field(..., ge=0, le=3)
    skipped_at_stage: Optional[int] = None
    skip_reason: Optional[str] = None

    # Metadata
    processing_time_ms: int = 0
    tokens_used: int = 0

    class Config:
        from_attributes = True


class VerifyDetailedResponse(VerifyResponse):
    """Detailed response including stage results (for debugging)."""

    # Stage 1 details
    stage1_score: Optional[float] = None
    is_duplicate: Optional[bool] = None
    subjectivity_score: Optional[float] = None
    fake_probability: Optional[float] = None

    # Stage 2 details
    check_worthy_score: Optional[float] = None
    has_existing_fact_check: Optional[bool] = None
    fact_check_ratings: list[str] = []

    # Stage 3 details
    verdict: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
