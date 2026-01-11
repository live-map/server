"""
Feed model for storing verified news items.

Includes pgvector embedding for duplicate detection.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Feed(Base):
    """
    Feed item model.

    Stores news/event data with verification metadata
    and embedding for similarity search.
    """

    __tablename__ = "feeds"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_link: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Source
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # RSS, TELEGRAM, API
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Classification
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # WAR, SECURITY
    sub_category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # ru-uk, is-ir, etc.

    # Location (extracted from Stage 1)
    location_lat: Mapped[float] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float] = mapped_column(Float, nullable=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # === Overall Verification Status ===
    credibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # verified, unverified, failed
    verification_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # True if any stage failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # Error details
    stages_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-3
    skipped_at_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Stage where skipped
    skip_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # === Stage 1: NLP Results ===
    stage1_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage1_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Overall quality score
    stage1_has_location: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage1_is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage1_subjectivity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    stage1_fake_prob: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0

    # === Stage 2: API Results ===
    stage2_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage2_check_worthy: Mapped[float | None] = mapped_column(Float, nullable=True)  # ClaimBuster score
    stage2_has_fact_check: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage2_fact_check_ratings: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array

    # === Stage 3: LLM Results ===
    stage3_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage3_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)  # TRUE, FALSE, PARTIALLY_TRUE, etc.
    stage3_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    stage3_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM explanation

    # Embedding for duplicate detection (all-MiniLM-L6-v2: 384 dimensions)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    # Timestamps
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Feed(id={self.id}, title='{self.title[:30]}...', status='{self.verification_status}')>"
