"""
PollComment model with self-referencing relationship for nested replies.

Follows the same pattern as the community Comment model.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.poll import Poll
    from app.models.poll_option import PollOption
    from app.models.user import User


class PollComment(Base):
    """
    여론조사 댓글 모델 (Self-Join 패턴으로 대댓글 지원).

    커뮤니티 Comment 모델과 동일 패턴에 option_id가 추가됨.
    - parent_id가 NULL이면 최상위 댓글
    - parent_id가 있으면 대댓글
    - option_id로 어느 편인지 표시 가능
    """

    __tablename__ = "poll_comments"

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

    # Foreign key to User
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Self-referencing foreign key
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("poll_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Option reference (어느 편인지)
    option_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("poll_options.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Comment content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

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
    poll: Mapped["Poll"] = relationship("Poll", back_populates="comments")
    user: Mapped["User"] = relationship("User", back_populates="poll_comments")
    option: Mapped[Optional["PollOption"]] = relationship("PollOption")

    # Self-referencing relationships
    parent: Mapped[Optional["PollComment"]] = relationship(
        "PollComment",
        remote_side=[id],
        back_populates="replies",
        foreign_keys=[parent_id],
    )
    replies: Mapped[list["PollComment"]] = relationship(
        "PollComment",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
    )

    def __repr__(self) -> str:
        return f"<PollComment(id={self.id}, poll_id={self.poll_id}, depth={self.depth})>"
