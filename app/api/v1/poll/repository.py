"""
Poll Repository - Data access layer for Poll model.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.poll import Poll
from app.models.poll_comment import PollComment
from app.models.poll_option import PollOption

logger = logging.getLogger(__name__)


def _escape_like(value: str) -> str:
    """LIKE/ILIKE 패턴 특수문자 이스케이프."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PollRepository:
    """Repository for Poll database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, poll: Poll) -> Poll:
        """새 여론조사 생성."""
        self.session.add(poll)
        await self.session.flush()
        await self.session.refresh(poll)
        logger.debug(f"Created poll: {poll.id}")
        return poll

    async def get_by_id(self, poll_id: uuid.UUID) -> Poll | None:
        """ID로 여론조사 조회."""
        stmt = select(Poll).where(Poll.id == poll_id, Poll.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_details(self, poll_id: uuid.UUID) -> Poll | None:
        """ID로 여론조사 조회 (옵션, 출처, 댓글, 작성자 포함)."""
        stmt = (
            select(Poll)
            .options(
                selectinload(Poll.options),
                selectinload(Poll.sources),
                selectinload(Poll.comments).selectinload(PollComment.user),
                selectinload(Poll.user),
            )
            .where(Poll.id == poll_id, Poll.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 20,
        offset: int = 0,
        sort: str = "popular",
        search: str | None = None,
        status: str | None = None,
        poll_type: str | None = None,
    ) -> Sequence[Poll]:
        """여론조사 목록 조회 (페이지네이션 + 정렬)."""
        stmt = (
            select(Poll)
            .options(
                selectinload(Poll.options),
                selectinload(Poll.user),
            )
            .where(Poll.is_deleted == False)
        )

        # 필터
        if status:
            stmt = stmt.where(Poll.status == status)
        if poll_type:
            stmt = stmt.where(Poll.type == poll_type)
        if search:
            safe = _escape_like(search)
            stmt = stmt.where(
                Poll.title.ilike(f"%{safe}%", escape="\\")
                | Poll.description.ilike(f"%{safe}%", escape="\\")
            )

        # 정렬
        now = datetime.now(timezone.utc)
        if sort == "recent":
            stmt = stmt.order_by(desc(Poll.created_at))
        elif sort == "ending_soon":
            stmt = stmt.where(Poll.status == "ACTIVE", Poll.ends_at > now)
            stmt = stmt.order_by(Poll.ends_at)
        elif sort == "closed":
            stmt = stmt.where(Poll.status == "CLOSED")
            stmt = stmt.order_by(desc(Poll.created_at))
        else:  # popular (default)
            stmt = stmt.order_by(desc(Poll.total_votes), desc(Poll.created_at))

        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        search: str | None = None,
        status: str | None = None,
        poll_type: str | None = None,
        sort: str = "popular",
    ) -> int:
        """여론조사 총 개수 (sort 필터 반영)."""
        stmt = select(func.count()).select_from(Poll).where(Poll.is_deleted == False)

        if status:
            stmt = stmt.where(Poll.status == status)
        if poll_type:
            stmt = stmt.where(Poll.type == poll_type)
        if search:
            safe = _escape_like(search)
            stmt = stmt.where(
                Poll.title.ilike(f"%{safe}%", escape="\\")
                | Poll.description.ilike(f"%{safe}%", escape="\\")
            )

        # sort 필터와 동일한 조건 적용
        now = datetime.now(timezone.utc)
        if sort == "ending_soon":
            stmt = stmt.where(Poll.status == "ACTIVE", Poll.ends_at > now)
        elif sort == "closed":
            stmt = stmt.where(Poll.status == "CLOSED")

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update(self, poll: Poll) -> Poll:
        """여론조사 수정."""
        await self.session.flush()
        await self.session.refresh(poll)
        logger.debug(f"Updated poll: {poll.id}")
        return poll

    async def soft_delete(self, poll_id: uuid.UUID) -> bool:
        """여론조사 소프트 삭제."""
        poll = await self.get_by_id(poll_id)
        if poll is None:
            raise ValueError(f"Poll with id {poll_id} not found")

        poll.is_deleted = True
        await self.session.flush()
        logger.debug(f"Soft deleted poll: {poll_id}")
        return True

    async def get_hot_debate(self) -> Poll | None:
        """핫 디베이트 조회 - 모든 타입 중 가장 접전인 poll.

        접전도 = 1위와 2위 옵션의 득표율 차이가 가장 작은 것.
        """
        stmt = (
            select(Poll)
            .options(
                selectinload(Poll.options),
                selectinload(Poll.comments).selectinload(PollComment.user),
            )
            .where(
                Poll.is_deleted == False,
                Poll.status == "ACTIVE",
                Poll.total_votes > 0,
            )
            .order_by(desc(Poll.total_votes))
            .limit(10)
        )
        result = await self.session.execute(stmt)
        polls = result.scalars().all()

        if not polls:
            return None

        # 가장 접전인 poll 찾기 (1위와 2위의 득표율 차이가 가장 작은 것)
        best_poll = polls[0]
        min_diff = float("inf")

        for poll in polls:
            if len(poll.options) < 2 or poll.total_votes == 0:
                continue
            # 득표수 기준 상위 2개 옵션
            sorted_opts = sorted(poll.options, key=lambda o: o.vote_count, reverse=True)
            pct_1st = (sorted_opts[0].vote_count / poll.total_votes) * 100
            pct_2nd = (sorted_opts[1].vote_count / poll.total_votes) * 100
            diff = abs(pct_1st - pct_2nd)
            if diff < min_diff:
                min_diff = diff
                best_poll = poll

        return best_poll

    async def atomic_increment_view_count(self, poll_id: uuid.UUID) -> None:
        """조회수 원자적 증가 (SQL UPDATE)."""
        stmt = (
            update(Poll)
            .where(Poll.id == poll_id, Poll.is_deleted == False)
            .values(view_count=Poll.view_count + 1)
        )
        await self.session.execute(stmt)

    async def get_suggested(self, limit: int = 10) -> Sequence[Poll]:
        """유저 제안 여론조사 목록."""
        stmt = (
            select(Poll)
            .options(
                selectinload(Poll.options),
                selectinload(Poll.user),
            )
            .where(
                Poll.is_deleted == False,
                Poll.status == "ACTIVE",
                Poll.type == "SUGGESTED",
            )
            .order_by(desc(Poll.view_count))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
