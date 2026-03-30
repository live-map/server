"""
PollComment Repository - Data access layer for PollComment model.

커뮤니티 CommentRepository와 동일한 패턴.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.poll_comment import PollComment

logger = logging.getLogger(__name__)


class PollCommentRepository:
    """Repository for PollComment database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, comment: PollComment) -> PollComment:
        """댓글 생성."""
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        logger.debug("Created poll comment: %s", comment.id)
        return comment

    async def get_by_id(self, comment_id: uuid.UUID) -> PollComment | None:
        """ID로 댓글 조회."""
        stmt = select(PollComment).where(
            PollComment.id == comment_id,
            PollComment.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_poll(
        self,
        poll_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Sequence[PollComment]:
        """여론조사의 모든 댓글 조회 (트리 구성용)."""
        stmt = (
            select(PollComment)
            .options(
                selectinload(PollComment.user),
                selectinload(PollComment.option),
            )
            .where(PollComment.poll_id == poll_id)
        )

        if not include_deleted:
            stmt = stmt.where(PollComment.is_deleted.is_(False))

        stmt = stmt.order_by(PollComment.created_at)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def soft_delete(self, comment: PollComment) -> bool:
        """댓글 소프트 삭제. 호출자가 이미 조회한 comment 객체를 전달."""
        comment.is_deleted = True
        # content는 DB에 보존 (관리/감사용). API 응답에서 service 레이어가 마스킹 처리
        await self.session.flush()
        logger.debug("Soft deleted poll comment: %s", comment.id)
        return True

    async def count_by_poll(self, poll_id: uuid.UUID) -> int:
        """여론조사의 댓글 수."""
        stmt = (
            select(func.count())
            .select_from(PollComment)
            .where(
                PollComment.poll_id == poll_id,
                PollComment.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
