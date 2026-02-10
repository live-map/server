"""
PostMedia model for storing media files attached to posts.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post


class MediaType(str, enum.Enum):
    """미디어 타입."""
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class PostMedia(Base):
    """
    게시글 미디어 모델.

    게시글에 첨부된 이미지 또는 비디오 파일 정보를 저장합니다.
    파일은 S3에 저장되고, 이 모델은 URL과 메타데이터만 저장합니다.

    Attributes:
        id: 미디어 UUID
        post_id: 게시글 UUID (FK)
        media_type: IMAGE 또는 VIDEO
        url: S3/CloudFront URL
        thumbnail_url: 비디오 썸네일 URL (비디오인 경우)
        original_filename: 원본 파일명
        file_size: 파일 크기 (bytes)
        duration: 비디오 길이 (초, 최대 60초)
        width: 이미지/비디오 너비 (픽셀)
        height: 이미지/비디오 높이 (픽셀)
        order: 표시 순서 (여러 미디어 시 정렬용)
        created_at: 생성 시간
    """

    __tablename__ = "post_media"

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

    # Media type (uses existing PostgreSQL enum "MediaType")
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="MediaType", create_type=False),
        nullable=False,
    )

    # URLs
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # File metadata
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds (video only, max 60)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)  # pixels
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)  # pixels

    # Display order (for multiple media)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="media")

    # Composite index for efficient ordering queries
    __table_args__ = (
        Index("ix_post_media_post_id_order", "post_id", "order"),
    )

    def __repr__(self) -> str:
        return f"<PostMedia(id={self.id}, type={self.media_type}, post_id={self.post_id})>"
