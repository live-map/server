"""
Feed model for storing verified news items.

Includes pgvector embedding for duplicate detection.
Supports social media sources (Telegram, X) with channel tracking.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # === Social Media Source (NEW) ===
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # TELEGRAM, X
    channel_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Platform message ID
    is_repost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    original_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Original post if repost
    channel_credibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0 at post time

    # Channel relationship
    channel = relationship("Channel", backref="feeds", lazy="selectin")

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
    stages_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-4 (includes Stage 0)
    skipped_at_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Stage where skipped
    skip_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # === Stage 0: Preprocessing Results (NEW) ===
    stage0_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Preprocessed text
    extracted_coordinates: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: [{lat, lng, format}]
    detected_terminology: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: [{term, normalized}]

    # === Stage 1: NLP Results ===
    stage1_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage1_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Overall quality score
    stage1_has_location: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage1_is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage1_subjectivity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0 (disabled for short posts)
    stage1_fake_prob: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0 (disabled for short posts)

    # === Stage 2: RAG Verification Results ===
    stage2_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage2_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SUPPORTED, REFUTED, UNCERTAIN
    stage2_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    stage2_evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # RAG evidence summary

    # === Stage 3: LLM Results ===
    stage3_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage3_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)  # TRUE, FALSE, PARTIALLY_TRUE, etc.
    stage3_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    stage3_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM explanation

    # Embedding for duplicate detection (BGE-M3: 1024 dimensions, multilingual)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)

    # === Publishable Status ===
    # Criteria: credibility >= 60, verified/partially_verified, has location, not duplicate
    is_publishable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Timestamps
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def check_publishable(self) -> bool:
        """
        Check if this feed meets publishable criteria.

        Criteria (v2 - social media optimized):
        - credibility_score >= 60
        - verification_status in ['verified', 'partially_verified']
        - not a duplicate (stage1_is_duplicate = False)
        - channel not blocked (if channel exists)

        Note: Location is now OPTIONAL - adds bonus but not required.
        Note: Subjectivity check disabled for short social media posts.
        """
        if self.credibility_score is None or self.credibility_score < 60:
            return False
        if self.verification_status not in ['verified', 'partially_verified']:
            return False
        if self.stage1_is_duplicate:
            return False
        # Check if channel is blocked
        if self.channel and self.channel.is_blocked:
            return False
        return True

    def __repr__(self) -> str:
        return f"<Feed(id={self.id}, title='{self.title[:30]}...', status='{self.verification_status}')>"
