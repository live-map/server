"""
Feed model for storing verified news items.

Includes pgvector embedding for duplicate detection.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text, func
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

    # Location
    location_lat: Mapped[float] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float] = mapped_column(Float, nullable=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Verification (Stage 1-3 pipeline results)
    credibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # verified, unverified, etc.
    fake_probability: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    subjectivity_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0

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
        return f"<Feed(id={self.id}, title='{self.title[:30]}...', category='{self.category}')>"
