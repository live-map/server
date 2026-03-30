"""
Post Repository - Data access layer for Post model.

Handles all database operations for posts.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.post import Post
from app.api.v1.post.sort import SortType, SIMPLE_SORT_MAP, TIME_WINDOW_MAP

logger = logging.getLogger(__name__)

class PostRepository:
    """
    Repository for Post database operations.

    모든 메서드는 SQLAlchemy 2.0 async 문법을 사용합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, post: Post) -> Post:
        """
        새 게시글 생성.

        Args:
            post: 생성할 Post 엔티티

        Returns:
            생성된 Post (ID가 할당됨)
        """
        self.session.add(post)
        await self.session.flush()  # ID 할당을 위해 flush
        await self.session.refresh(post)
        logger.debug(f"Created post: {post.id}")
        return post

    async def get_by_id(self, post_id: uuid.UUID) -> Post | None:
        """
        ID로 게시글 조회.

        Args:
            post_id: 게시글 UUID

        Returns:
            Post | None: 게시글 또는 None
        """
        stmt = select(Post).where(Post.id == post_id, Post.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_comments(self, post_id: uuid.UUID) -> Post | None:
        """
        ID로 게시글 조회 (댓글, 미디어 포함).

        Eager loading으로 댓글과 미디어를 함께 로드합니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            Post | None: 댓글과 미디어가 포함된 게시글
        """
        stmt = (
            select(Post)
            .options(
                selectinload(Post.comments).selectinload(Comment.user),  # 댓글 + 작성자 eager load
                selectinload(Post.user),      # 작성자 eager load
                selectinload(Post.media),     # 미디어 eager load
            )
            .where(Post.id == post_id, Post.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: str | None = None,
        sort: SortType = SortType.NEWEST,
    ) -> Sequence[Post]:
        """
        게시글 목록 조회 (페이지네이션 + 정렬).

        Args:
            limit: 최대 조회 수
            offset: 건너뛸 수
            user_id: 특정 사용자의 글만 조회 (선택)
            sort: 정렬 기준

        Returns:
            Sequence[Post]: 게시글 목록
        """
        stmt = (
            select(Post)
            .options(
                selectinload(Post.user),      # 작성자 eager load
                selectinload(Post.media),     # 미디어 eager load
            )
            .where(Post.is_deleted == False)
        )

        if user_id:
            stmt = stmt.where(Post.user_id == user_id)

        # Time-windowed sorts: add WHERE created_at >= cutoff
        if sort in TIME_WINDOW_MAP:
            cutoff = datetime.now(timezone.utc) - TIME_WINDOW_MAP[sort]
            stmt = stmt.where(Post.created_at >= cutoff)
            stmt = stmt.order_by(desc(Post.popularity_score), desc(Post.created_at))
        else:
            # Simple sorts: use mapped ORDER BY columns
            order_clauses = SIMPLE_SORT_MAP.get(sort, [desc(Post.created_at)])
            stmt = stmt.order_by(*order_clauses)

        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, post: Post) -> Post:
        """
        게시글 수정.

        Args:
            post: 수정할 Post 엔티티 (이미 변경된 상태)

        Returns:
            수정된 Post
        """
        await self.session.flush()
        await self.session.refresh(post)
        logger.debug(f"Updated post: {post.id}")
        return post

    async def soft_delete(self, post_id: uuid.UUID) -> bool:
        """
        게시글 소프트 삭제.

        Args:
            post_id: 삭제할 게시글 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        post = await self.get_by_id(post_id)
        if post is None:
            raise ValueError(f"Post with id {post_id} not found")

        post.is_deleted = True
        await self.session.flush()
        logger.debug(f"Soft deleted post: {post_id}")
        return True

    async def hard_delete(self, post_id: uuid.UUID) -> bool:
        """
        !!! 게시글 완전 삭제 (DB에서 영구 삭제!) !!! 
        !!! admin 만 사용할 수 있는 메서드!!! 
        
        게시글 완전 삭제 (DB에서 영구 삭제!).

        CASCADE 설정으로 인해 해당 게시글의 모든 댓글과
        대댓글도 함께 삭제됩니다.

        Args:
            post_id: 삭제할 게시글 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        # is_deleted 상태와 관계없이 조회
        stmt = select(Post).where(Post.id == post_id)
        result = await self.session.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ValueError(f"Post with id {post_id} not found")

        await self.session.delete(post)
        await self.session.flush()
        logger.debug(f"Hard deleted post: {post_id} (with all comments via CASCADE)")
        return True

    async def count(
        self,
        user_id: str | None = None,
        sort: SortType = SortType.NEWEST,
    ) -> int:
        """
        게시글 총 개수.

        Args:
            user_id: 특정 사용자의 글만 카운트 (선택)
            sort: 정렬 기준 (시간 윈도우 필터 적용용)

        Returns:
            int: 게시글 수
        """
        stmt = select(func.count()).select_from(Post).where(Post.is_deleted == False)

        if user_id:
            stmt = stmt.where(Post.user_id == user_id)

        if sort in TIME_WINDOW_MAP:
            cutoff = datetime.now(timezone.utc) - TIME_WINDOW_MAP[sort]
            stmt = stmt.where(Post.created_at >= cutoff)

        result = await self.session.execute(stmt)
        return result.scalar_one()