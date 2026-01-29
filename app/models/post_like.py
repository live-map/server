"""
PostLike model for tracking user likes on posts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class PostLike(Base):
    """
    게시글 좋아요 모델.

    어떤 사용자가 어떤 게시글에 좋아요를 눌렀는지 추적합니다.
    (post_id, user_id) 조합은 unique하여 중복 좋아요를 방지합니다.

    Attributes:
        id: 좋아요 UUID
        post_id: 게시글 UUID (FK)
        user_id: 사용자 ID (FK)
        created_at: 좋아요 시간
    """

    __tablename__ = "post_likes"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to Post
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
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
    post: Mapped["Post"] = relationship("Post", back_populates="likes")
    user: Mapped["User"] = relationship("User", back_populates="post_likes")

    # Unique constraint to prevent duplicate likes
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )

    def __repr__(self) -> str:
        return f"<PostLike(post_id={self.post_id}, user_id={self.user_id})>"
