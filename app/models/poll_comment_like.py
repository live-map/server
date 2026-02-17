"""
PollCommentLike model for tracking user likes on poll comments.

Prevents duplicate likes via (comment_id, user_id) unique constraint.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.poll_comment import PollComment
    from app.models.user import User


class PollCommentLike(Base):
    """
    여론조사 댓글 좋아요 모델.

    어떤 사용자가 어떤 댓글에 좋아요를 눌렀는지 추적합니다.
    (comment_id, user_id) 조합은 unique하여 중복 좋아요를 방지합니다.
    """

    __tablename__ = "poll_comment_likes"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_poll_comment_like_comment_user"),
    )

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to PollComment
    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("poll_comments.id", ondelete="CASCADE"),
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

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    comment: Mapped["PollComment"] = relationship("PollComment", back_populates="comment_likes")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<PollCommentLike(comment_id={self.comment_id}, user_id={self.user_id})>"
