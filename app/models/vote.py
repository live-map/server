"""
Vote model for poll voting.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.poll import Poll
    from app.models.poll_option import PollOption
    from app.models.user import User


class Vote(Base):
    """
    투표 모델.

    사용자의 투표를 저장합니다.
    interactionType에 따라 다른 필드를 사용합니다:
    - BINARY, SINGLE_CHOICE, EMOJI_REACTION → option_id
    - SLIDER → slider_value
    - MULTIPLE_CHOICE → selected_option_ids (JSON)
    - RANKING → ranking_data (JSON)
    """

    __tablename__ = "votes"

    # Unique constraint: 한 사용자는 한 여론조사에 한 번만 투표
    __table_args__ = (
        UniqueConstraint("user_id", "poll_id", name="uq_votes_user_poll"),
    )

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    poll_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("polls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("poll_options.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Interaction-type-specific fields
    slider_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_option_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ranking_data: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="votes")
    poll: Mapped["Poll"] = relationship("Poll", back_populates="votes")
    option: Mapped[Optional["PollOption"]] = relationship("PollOption", back_populates="votes")

    def __repr__(self) -> str:
        return f"<Vote(id={self.id}, user_id={self.user_id}, poll_id={self.poll_id})>"
