"""
PollOption model for poll choices.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.poll import Poll
    from app.models.vote import Vote


class PollOption(Base):
    """
    여론조사 선택지 모델.

    각 여론조사는 여러 선택지를 가집니다.
    """

    __tablename__ = "poll_options"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to Poll
    poll_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("polls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Option content
    text: Mapped[str] = mapped_column(String(200), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Denormalized counter
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    poll: Mapped["Poll"] = relationship("Poll", back_populates="options")
    votes: Mapped[list["Vote"]] = relationship("Vote", back_populates="option")

    def __repr__(self) -> str:
        return f"<PollOption(id={self.id}, text='{self.text[:20]}')>"
