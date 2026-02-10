"""
PostMedia Repository - Data access layer for PostMedia model.

Handles all database operations for post media (images/videos).
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post_media import PostMedia

logger = logging.getLogger(__name__)


class PostMediaRepository:
    """
    Repository for PostMedia database operations.

    미디어 파일의 메타데이터를 관리합니다.
    실제 파일은 S3에 저장되고, 이 레포지토리는 URL과 메타데이터만 다룹니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, media: PostMedia) -> PostMedia:
        """
        새 미디어 레코드 생성.

        Args:
            media: 생성할 PostMedia 엔티티

        Returns:
            생성된 PostMedia (ID가 할당됨)
        """
        self.session.add(media)
        await self.session.flush()
        await self.session.refresh(media)
        logger.debug(f"Created media: {media.id} for post {media.post_id}")
        return media

    async def create_many(self, media_list: list[PostMedia]) -> list[PostMedia]:
        """
        여러 미디어 레코드 일괄 생성.

        Args:
            media_list: 생성할 PostMedia 엔티티 목록

        Returns:
            생성된 PostMedia 목록
        """
        self.session.add_all(media_list)
        await self.session.flush()
        for media in media_list:
            await self.session.refresh(media)
        logger.debug(f"Created {len(media_list)} media records")
        return media_list

    async def get_by_id(self, media_id: uuid.UUID) -> PostMedia | None:
        """
        ID로 미디어 조회.

        Args:
            media_id: 미디어 UUID

        Returns:
            PostMedia | None
        """
        stmt = select(PostMedia).where(PostMedia.id == media_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_post_id(self, post_id: uuid.UUID) -> Sequence[PostMedia]:
        """
        게시글의 모든 미디어 조회.

        Args:
            post_id: 게시글 UUID

        Returns:
            Sequence[PostMedia]: 미디어 목록 (order 순으로 정렬)
        """
        stmt = (
            select(PostMedia)
            .where(PostMedia.post_id == post_id)
            .order_by(PostMedia.order)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete(self, media_id: uuid.UUID) -> bool:
        """
        미디어 레코드 삭제.

        Note: S3의 실제 파일은 별도로 삭제해야 합니다.

        Args:
            media_id: 삭제할 미디어 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        media = await self.get_by_id(media_id)
        if media is None:
            return False

        await self.session.delete(media)
        await self.session.flush()
        logger.debug(f"Deleted media: {media_id}")
        return True

    async def delete_by_post_id(self, post_id: uuid.UUID) -> int:
        """
        게시글의 모든 미디어 삭제.

        Note: S3의 실제 파일은 별도로 삭제해야 합니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 삭제된 미디어 수
        """
        stmt = delete(PostMedia).where(PostMedia.post_id == post_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        deleted_count = result.rowcount
        logger.debug(f"Deleted {deleted_count} media records for post {post_id}")
        return deleted_count

    async def update_order(self, media_id: uuid.UUID, new_order: int) -> PostMedia | None:
        """
        미디어 표시 순서 변경.

        Args:
            media_id: 미디어 UUID
            new_order: 새 순서 값

        Returns:
            수정된 PostMedia | None
        """
        media = await self.get_by_id(media_id)
        if media is None:
            return None

        media.order = new_order
        await self.session.flush()
        await self.session.refresh(media)
        return media

    async def count_by_post_id(self, post_id: uuid.UUID) -> int:
        """
        게시글의 미디어 개수.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 미디어 수
        """
        stmt = (
            select(func.count())
            .select_from(PostMedia)
            .where(PostMedia.post_id == post_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
