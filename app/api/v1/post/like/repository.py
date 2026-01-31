"""
PostLike Repository - Data access layer for PostLike model.

Handles all database operations for post likes.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.post_like import PostLike

logger = logging.getLogger(__name__)


class PostLikeRepository:
    """
    Repository for PostLike database operations.

    좋아요 데이터와 Post.like_count 동기화를 관리합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, like: PostLike) -> PostLike:
        """
        좋아요 생성.

        Args:
            like: 생성할 PostLike 엔티티

        Returns:
            생성된 PostLike
        """
        self.session.add(like)
        await self.session.flush()
        await self.session.refresh(like)
        logger.debug(f"Created like: user {like.user_id} -> post {like.post_id}")
        return like

    async def delete(self, post_id: uuid.UUID, user_id: str) -> bool:
        """
        좋아요 삭제.

        Args:
            post_id: 게시글 UUID
            user_id: 사용자 ID

        Returns:
            bool: 삭제 성공 여부
        """
        stmt = delete(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Deleted like: user {user_id} -> post {post_id}")
        return deleted

    async def exists(self, post_id: uuid.UUID, user_id: str) -> bool:
        """
        좋아요 존재 여부 확인.

        Args:
            post_id: 게시글 UUID
            user_id: 사용자 ID

        Returns:
            bool: 좋아요 여부
        """
        stmt = select(PostLike.id).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_post_id(
        self,
        post_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[PostLike]:
        """
        게시글의 좋아요 목록 조회.

        Args:
            post_id: 게시글 UUID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[PostLike]: 좋아요 목록 (최신순, user 정보 포함)
        """
        stmt = (
            select(PostLike)
            .options(selectinload(PostLike.user))  # user 정보 eager load
            .where(PostLike.post_id == post_id)
            .order_by(PostLike.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_user_liked_posts(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[PostLike]:
        """
        사용자가 좋아요한 게시글 목록 조회.

        Args:
            user_id: 사용자 ID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[PostLike]: 좋아요 목록 (최신순)
        """
        stmt = (
            select(PostLike)
            .where(PostLike.user_id == user_id)
            .order_by(PostLike.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_post_id(self, post_id: uuid.UUID) -> int:
        """
        게시글의 좋아요 수.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 좋아요 수
        """
        stmt = (
            select(func.count())
            .select_from(PostLike)
            .where(PostLike.post_id == post_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def check_post_exists_and_active(self, post_id: uuid.UUID) -> bool:
        """
        게시글 존재 및 활성 상태 확인.

        Race condition 방지를 위해 좋아요 전 게시글 상태를 확인합니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            bool: 게시글이 존재하고 삭제되지 않았으면 True
        """
        stmt = select(Post.id).where(
            Post.id == post_id,
            Post.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def increment_like_count(self, post_id: uuid.UUID) -> bool:
        """
        Post.like_count 증가.

        is_deleted=False인 게시글에만 적용됩니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            bool: 업데이트 성공 여부 (False면 게시글이 삭제됨)
        """
        stmt = (
            update(Post)
            .where(Post.id == post_id, Post.is_deleted == False)
            .values(like_count=Post.like_count + 1)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        updated = result.rowcount > 0
        if updated:
            logger.debug(f"Incremented like_count for post {post_id}")
        else:
            logger.warning(f"Failed to increment like_count for post {post_id} (deleted?)")
        return updated

    async def decrement_like_count(self, post_id: uuid.UUID) -> bool:
        """
        Post.like_count 감소.

        like_count > 0 일 때만 감소합니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            bool: 업데이트 성공 여부 (False면 이미 0이거나 게시글 없음)
        """
        stmt = (
            update(Post)
            .where(Post.id == post_id, Post.like_count > 0)
            .values(like_count=Post.like_count - 1)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        updated = result.rowcount > 0
        if updated:
            logger.debug(f"Decremented like_count for post {post_id}")
        else:
            logger.warning(f"Failed to decrement like_count for post {post_id} (already 0 or not found)")
        return updated

    async def get_like_status_for_posts(
        self,
        post_ids: list[uuid.UUID],
        user_id: str,
    ) -> dict[uuid.UUID, bool]:
        """
        여러 게시글에 대한 사용자의 좋아요 상태 일괄 조회.

        게시글 목록 조회 시 N+1 문제를 방지하기 위해 사용합니다.

        Args:
            post_ids: 게시글 UUID 목록
            user_id: 사용자 ID

        Returns:
            dict[UUID, bool]: {post_id: is_liked}
        """
        stmt = select(PostLike.post_id).where(
            PostLike.post_id.in_(post_ids),
            PostLike.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        liked_post_ids = set(result.scalars().all())

        return {post_id: post_id in liked_post_ids for post_id in post_ids}
