"""
Poll Service - Business logic for polls.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.poll.repository import PollRepository
from app.models.poll import Poll
from app.models.poll_option import PollOption
from app.models.poll_source import PollSource

logger = logging.getLogger(__name__)


# ========================================
# Custom Exceptions
# ========================================

class PollNotFoundError(Exception):
    """여론조사가 존재하지 않을 때."""
    pass


class PollPermissionError(Exception):
    """권한이 없을 때."""
    pass


class PollService:
    """Poll 관련 비즈니스 로직."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.poll_repo = PollRepository(session)

    async def create_poll(
        self,
        user_id: str,
        title: str,
        description: str | None,
        image_url: str | None,
        category: str | None,
        interaction_type: str,
        starts_at=None,
        ends_at=None,
        options: list[dict] | None = None,
        sources: list[dict] | None = None,
    ) -> Poll:
        """여론조사 생성 (제안)."""
        poll = Poll(
            user_id=user_id,
            title=title,
            description=description,
            image_url=image_url,
            category=category,
            type="SUGGESTED",
            status="ACTIVE",
            interaction_type=interaction_type,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        created = await self.poll_repo.create(poll)

        # 선택지 추가
        if options:
            for i, opt in enumerate(options):
                option = PollOption(
                    poll_id=created.id,
                    text=opt["text"],
                    order=opt.get("order", i),
                )
                self.session.add(option)

        # 출처 추가
        if sources:
            for src in sources:
                source = PollSource(
                    poll_id=created.id,
                    title=src["title"],
                    url=src["url"],
                    source_type=src.get("source_type", "OTHER"),
                    description=src.get("description"),
                )
                self.session.add(source)

        await self.session.commit()
        # 관계 데이터 포함하여 다시 로드
        poll = await self.poll_repo.get_by_id_with_details(created.id)
        logger.info(f"Poll created: {created.id} by user {user_id}")
        return poll

    async def get_poll(self, poll_id: uuid.UUID) -> Poll | None:
        """여론조사 조회."""
        return await self.poll_repo.get_by_id(poll_id)

    async def get_poll_with_details(self, poll_id: uuid.UUID) -> Poll | None:
        """여론조사 상세 조회."""
        return await self.poll_repo.get_by_id_with_details(poll_id)

    async def list_polls(
        self,
        limit: int = 20,
        offset: int = 0,
        sort: str = "popular",
        search: str | None = None,
    ) -> Sequence[Poll]:
        """여론조사 목록 조회."""
        return await self.poll_repo.get_all(
            limit=limit, offset=offset, sort=sort, search=search,
        )

    async def count_polls(
        self, search: str | None = None, sort: str = "popular"
    ) -> int:
        """여론조사 총 개수 (sort 필터 반영)."""
        return await self.poll_repo.count(search=search, sort=sort)

    async def update_poll(
        self,
        poll_id: uuid.UUID,
        user_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> Poll:
        """여론조사 수정."""
        poll = await self.poll_repo.get_by_id(poll_id)
        if poll is None:
            raise PollNotFoundError(f"Poll {poll_id} not found")
        if poll.user_id != user_id:
            raise PollPermissionError(f"User {user_id} is not the owner of poll {poll_id}")

        if title is not None:
            poll.title = title
        if description is not None:
            poll.description = description
        if status is not None:
            poll.status = status

        updated = await self.poll_repo.update(poll)
        await self.session.commit()
        return updated

    async def delete_poll(self, poll_id: uuid.UUID, user_id: str) -> bool:
        """여론조사 삭제."""
        poll = await self.poll_repo.get_by_id(poll_id)
        if poll is None:
            raise PollNotFoundError(f"Poll {poll_id} not found")
        if poll.user_id != user_id:
            raise PollPermissionError(f"User {user_id} is not the owner of poll {poll_id}")

        result = await self.poll_repo.soft_delete(poll_id)
        await self.session.commit()
        return result

    async def get_hot_debate(self) -> Poll | None:
        """핫 디베이트 조회."""
        return await self.poll_repo.get_hot_debate()

    async def get_suggested_polls(self, limit: int = 10) -> Sequence[Poll]:
        """유저 제안 목록."""
        return await self.poll_repo.get_suggested(limit)

    async def increment_view_count(self, poll_id: uuid.UUID) -> None:
        """조회수 원자적 증가."""
        await self.poll_repo.atomic_increment_view_count(poll_id)
        await self.session.commit()
