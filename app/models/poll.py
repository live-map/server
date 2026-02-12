"""
Poll model for the survey/polling system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.poll_comment import PollComment
    from app.models.poll_option import PollOption
    from app.models.poll_source import PollSource
    from app.models.user import User
    from app.models.vote import Vote


class PollType(str, Enum):
    """여론조사 유형."""
    OFFICIAL = "OFFICIAL"
    SUGGESTED = "SUGGESTED"


class PollStatus(str, Enum):
    """여론조사 상태."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class InteractionType(str, Enum):
    """투표 인터랙션 유형."""
    BINARY = "BINARY"
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    SLIDER = "SLIDER"
    EMOJI_REACTION = "EMOJI_REACTION"
    RANKING = "RANKING"


class Poll(Base):
    """
    여론조사 모델.

    각 여론조사는 여러 옵션, 출처, 댓글, 투표를 가질 수 있습니다.
    """

    __tablename__ = "polls"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to User
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Poll content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Type and status
    type: Mapped[str] = mapped_column(
        String(20), default=PollType.SUGGESTED.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=PollStatus.ACTIVE.value, nullable=False
    )
    interaction_type: Mapped[str] = mapped_column(
        String(30), default=InteractionType.SINGLE_CHOICE.value, nullable=False
    )

    # Denormalized counters
    total_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # AI analysis
    ai_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Time window
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="polls")
    options: Mapped[list["PollOption"]] = relationship(
        "PollOption",
        back_populates="poll",
        cascade="all, delete-orphan",
        order_by="PollOption.order",
    )
    sources: Mapped[list["PollSource"]] = relationship(
        "PollSource",
        back_populates="poll",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["PollComment"]] = relationship(
        "PollComment",
        back_populates="poll",
        cascade="all, delete-orphan",
    )
    votes: Mapped[list["Vote"]] = relationship(
        "Vote",
        back_populates="poll",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Poll(id={self.id}, title='{self.title[:30]}...')>"
