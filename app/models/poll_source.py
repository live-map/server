"""
PollSource model for poll reference sources.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.poll import Poll


class SourceType(str, Enum):
    """출처 유형."""
    NEWS = "NEWS"
    PAPER = "PAPER"
    ARTICLE = "ARTICLE"
    VIDEO = "VIDEO"
    OTHER = "OTHER"


class PollSource(Base):
    """
    여론조사 출처 모델.

    여론조사에 참고 자료(뉴스, 논문 등)를 첨부합니다.
    """

    __tablename__ = "poll_sources"

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

    # Source content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(20), default=SourceType.OTHER.value, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    poll: Mapped["Poll"] = relationship("Poll", back_populates="sources")

    def __repr__(self) -> str:
        return f"<PollSource(id={self.id}, title='{self.title[:20]}')>"
