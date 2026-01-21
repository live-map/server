"""
Event model for tracking news events (story chains).

Used for:
- Deduplication: Prevent duplicate articles for the same event
- Update detection: Allow new articles when significant updates occur
- Story tracking: Link related articles over time
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Event(Base):
    """
    Event model representing a unique news event.

    An event is a specific occurrence that may be covered by multiple sources.
    Articles are linked to events for deduplication and story tracking.
    """

    __tablename__ = "events"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Unique identifier for fast hash-based lookup
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Canonical title (representative title for the event)
    canonical_title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Embedding for semantic similarity search (BGE-M3: 1024 dimensions)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)

    # === Key Facts (for update detection) ===
    key_entities: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: people, places, orgs
    key_facts: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: list of factual claims
    fact_hash: Mapped[str] = mapped_column(String(64), index=True)  # Hash of key facts for quick comparison

    # Classification
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    sub_category: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)

    # === Statistics ===
    first_reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    article_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship to articles
    articles = relationship("Article", back_populates="event", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title='{self.canonical_title[:30]}...', articles={self.article_count})>"
