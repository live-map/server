"""
Vote Repository - Data access layer for Vote model.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vote import Vote

logger = logging.getLogger(__name__)


class VoteRepository:
    """Repository for Vote database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, vote: Vote) -> Vote:
        """투표 생성."""
        self.session.add(vote)
        await self.session.flush()
        await self.session.refresh(vote)
        logger.debug("Created vote: %s", vote.id)
        return vote

    async def get_by_user_and_poll(
        self, user_id: str, poll_id: uuid.UUID
    ) -> Vote | None:
        """사용자의 특정 여론조사 투표 조회."""
        stmt = select(Vote).where(
            Vote.user_id == user_id,
            Vote.poll_id == poll_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_votes_for_polls(
        self, user_id: str, poll_ids: list[uuid.UUID]
    ) -> Sequence[Vote]:
        """사용자의 여러 여론조사 투표 상태 일괄 조회."""
        if not poll_ids:
            return []
        stmt = select(Vote).where(
            Vote.user_id == user_id,
            Vote.poll_id.in_(poll_ids),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_average_slider_value(self, poll_id: uuid.UUID) -> float | None:
        """SLIDER 타입 poll의 평균 슬라이더 값을 SQL로 계산."""
        stmt = select(func.avg(Vote.slider_value)).where(
            Vote.poll_id == poll_id,
            Vote.slider_value.is_not(None),
        )
        result = await self.session.execute(stmt)
        avg = result.scalar_one_or_none()
        return round(float(avg), 1) if avg is not None else None
