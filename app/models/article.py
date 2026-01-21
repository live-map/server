"""
Article model for storing bilingual news articles.

Features:
- Bilingual storage (English + Korean)
- Linked to events for story tracking
- Verification metadata
- Update tracking
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ArticleStatus(str, Enum):
    """Article publication status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class UpdateType(str, Enum):
    """Type of update for follow-up articles."""

    INITIAL = "initial"  # First article for event
    NEW_DEVELOPMENT = "new_development"  # New actions/reactions
    CASUALTY_UPDATE = "casualty_update"  # Casualty numbers changed
    STATUS_CHANGE = "status_change"  # Ceasefire, escalation
    GEOGRAPHIC_EXPANSION = "geographic_expansion"  # New locations
    CORRECTION = "correction"  # Correcting previous article


class Article(Base):
    """
    Bilingual article model.

    Stores both English and Korean versions of the article,
    linked to an event for deduplication and story tracking.
    """

    __tablename__ = "articles"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Link to event
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Update tracking
    is_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    update_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    update_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # === English Content ===
    headline_en: Mapped[str] = mapped_column(String(500), nullable=False)
    lead_en: Mapped[str] = mapped_column(Text, nullable=False)  # Opening paragraph
    nut_graph_en: Mapped[str | None] = mapped_column(Text, nullable=True)  # Context paragraph
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    full_text_en: Mapped[str] = mapped_column(Text, nullable=False)  # Complete article

    # === Korean Content ===
    headline_ko: Mapped[str] = mapped_column(String(500), nullable=False)
    lead_ko: Mapped[str] = mapped_column(Text, nullable=False)
    nut_graph_ko: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_ko: Mapped[str] = mapped_column(Text, nullable=False)
    full_text_ko: Mapped[str] = mapped_column(Text, nullable=False)

    # === Verification Metadata ===
    claims_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claims_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claims_refuted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claims_unverifiable: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Source tracking
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of sources

    # === Status ===
    status: Mapped[str] = mapped_column(
        String(20), default=ArticleStatus.PUBLISHED.value, nullable=False, index=True
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # === Timestamps ===
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship to event
    event = relationship("Event", back_populates="articles")

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, headline_en='{self.headline_en[:30]}...', event_id={self.event_id})>"
