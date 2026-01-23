"""
Comment model with self-referencing relationship for nested replies.

This implements the self-join pattern where a comment can have:
- A parent post (required)
- A parent comment (optional, for replies)
- Multiple child comments (replies to this comment)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Comment(Base):
    """
    댓글 모델 (Self-Join 패턴으로 대댓글 지원).

    주요 특징:
    - parent_id가 NULL이면 최상위 댓글
    - parent_id가 있으면 해당 댓글의 대댓글
    - depth로 계층 깊이 관리
    - order_number로 같은 그룹 내 정렬
    """

    __tablename__ = "comments"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to Post (UUID - 필수, 모든 댓글은 게시글에 소속)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Foreign key to User (작성자)
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Self-referencing foreign key (UUID - 부모 댓글, 대댓글인 경우에만 값 있음)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,  # NULL이면 최상위 댓글
        index=True,
    )

    # Comment content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Hierarchy information
    depth: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="댓글 깊이: 0=최상위, 1=대댓글, 2=대대댓글...",
    )
    order_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="같은 그룹 내 정렬 순서",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Soft delete (대댓글이 있는 경우 구조 유지를 위해 soft delete 사용)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ========================================
    # Relationships
    # ========================================

    # 게시글과의 관계
    post: Mapped["Post"] = relationship("Post", back_populates="comments")

    # 작성자와의 관계
    user: Mapped["User"] = relationship("User", back_populates="comments")

    # Self-referencing relationships (대댓글 구조)
    # 부모 댓글 (이 댓글이 대댓글인 경우)
    parent: Mapped[Optional["Comment"]] = relationship(
        "Comment",
        remote_side=[id],  # 자기 참조 시 어느 쪽이 "1" 쪽인지 명시
        back_populates="replies",
        foreign_keys=[parent_id],
    )

    # 자식 댓글들 (이 댓글의 대댓글들)
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, post_id={self.post_id}, depth={self.depth})>"

    @property
    def is_reply(self) -> bool:
        """대댓글인지 여부."""
        return self.parent_id is not None

    @property
    def reply_count(self) -> int:
        """직접 대댓글 수 (lazy load 주의)."""
        return len(self.replies) if self.replies else 0
