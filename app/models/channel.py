"""
Channel model for storing source channel information.

Tracks Telegram channels, X accounts with credibility metrics.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Channel(Base):
    """
    Channel/account model for social media sources.

    Stores metadata and calculated credibility scores for
    Telegram channels and X (Twitter) accounts.
    """

    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("platform", "platform_channel_id", name="uq_channel_platform_id"),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Platform identification
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # TELEGRAM, X
    platform_channel_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Platform-specific ID
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)  # @username
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Channel metadata
    subscriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO 639-1

    # Credibility metrics (calculated)
    credibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    tier: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 1 (best) - 5 (unknown)

    # Historical accuracy tracking
    total_posts_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posts_verified_true: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posts_verified_false: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posts_unverifiable: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    historical_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0

    # Manual overrides
    is_trusted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # Manual trust override
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Block this channel
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)  # Admin notes

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    credibility_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def calculate_historical_accuracy(self) -> float | None:
        """
        Calculate historical accuracy from verified posts.

        Returns None if insufficient data (< 10 posts analyzed).
        """
        if self.total_posts_analyzed < 10:
            return None

        verifiable = self.posts_verified_true + self.posts_verified_false
        if verifiable == 0:
            return None

        return self.posts_verified_true / verifiable

    def update_accuracy_stats(self, verdict: str) -> None:
        """
        Update accuracy statistics based on verification verdict.

        Args:
            verdict: One of TRUE, FALSE, UNVERIFIABLE
        """
        self.total_posts_analyzed += 1

        if verdict == "TRUE":
            self.posts_verified_true += 1
        elif verdict == "FALSE":
            self.posts_verified_false += 1
        else:
            self.posts_unverifiable += 1

        self.historical_accuracy = self.calculate_historical_accuracy()

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, platform='{self.platform}', username='{self.username}', tier={self.tier})>"
