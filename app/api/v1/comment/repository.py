"""
Comment Repository - Data access layer for Comment model.

Handles all database operations for comments including nested replies.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment

logger = logging.getLogger(__name__)


class CommentRepository:
    """
    Repository for Comment database operations.

    대댓글 구조를 위한 Self-Join 쿼리를 처리합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, comment: Comment) -> Comment:
        """
        새 댓글/대댓글 생성.

        Args:
            comment: 생성할 Comment 엔티티

        Returns:
            생성된 Comment (ID 할당됨)
        """
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        logger.debug(f"Created comment: {comment.id}, depth: {comment.depth}")
        return comment

    async def get_by_id(self, comment_id: uuid.UUID) -> Comment | None:
        """
        ID로 댓글 조회.


        Args:
            comment_id: 댓글 UUID

        Returns:
            Comment | None
        """
        stmt = (
            select(Comment)
            .options(selectinload(Comment.user))  # 작성자 eager load
            .where(
                Comment.id == comment_id,
                Comment.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_replies(self, comment_id: uuid.UUID) -> Comment | None:
        """
        ID로 댓글 조회 (대댓글 포함).

        Args:
            comment_id: 댓글 UUID

        Returns:
            Comment | None: 대댓글이 포함된 댓글
        """
        stmt = (
            select(Comment)
            .options(
                selectinload(Comment.replies),  # 직접 대댓글 eager load
                selectinload(Comment.user),     # 작성자 eager load
            )
            .where(Comment.id == comment_id, Comment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_top_level_comments(
        self,
        post_id: uuid.UUID,
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[Comment]:
        """
        게시글의 최상위 댓글만 조회 (depth=0, parent_id=NULL).

        대댓글은 별도로 로드하거나 eager loading 사용.

        Args:
            post_id: 게시글 UUID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[Comment]: 최상위 댓글 목록
        """
        stmt = (
            select(Comment)
            .options(
                selectinload(Comment.user),
                selectinload(Comment.replies).selectinload(Comment.user),
            )
            .where(
                Comment.post_id == post_id,
                Comment.parent_id == None,  # 최상위 댓글만
                Comment.is_deleted == False,
            )
            .order_by(Comment.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_comments_by_post(
        self,
        post_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Sequence[Comment]:
        """
        게시글의 모든 댓글 조회 (계층 구조 포함).

        order_number와 depth로 정렬하여 계층 순서대로 반환.

        Args:
            post_id: 게시글 UUID
            include_deleted: 삭제된 댓글 포함 여부

        Returns:
            Sequence[Comment]: 모든 댓글 (계층 순서)
        """
        conditions = [Comment.post_id == post_id]

        if not include_deleted:
            conditions.append(Comment.is_deleted == False)

        stmt = (
            select(Comment)
            .options(selectinload(Comment.user))
            .where(and_(*conditions))
            .order_by(
                Comment.order_number.asc(),  # 그룹 순서
                Comment.depth.asc(),         # 깊이 순서
                Comment.created_at.asc(),    # 생성 시간
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_replies(
        self,
        parent_id: uuid.UUID,
        limit: int = 50,
    ) -> Sequence[Comment]:
        """
        특정 댓글의 직접 대댓글만 조회.

        Args:
            parent_id: 부모 댓글 UUID
            limit: 최대 조회 수

        Returns:
            Sequence[Comment]: 대댓글 목록
        """
        stmt = (
            select(Comment)
            .options(selectinload(Comment.user))
            .where(
                Comment.parent_id == parent_id,
                Comment.is_deleted == False,
            )
            .order_by(Comment.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_next_order_number(self, post_id: uuid.UUID) -> int:
        """
        새 최상위 댓글의 order_number 계산.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 다음 order_number
        """
        stmt = (
            select(func.coalesce(func.max(Comment.order_number), 0))
            .where(Comment.post_id == post_id)
        )
        result = await self.session.execute(stmt)
        max_order = result.scalar_one()
        return max_order + 1

    async def update(self, comment: Comment) -> Comment:
        """
        댓글 수정.

        Args:
            comment: 수정할 Comment 엔티티

        Returns:
            수정된 Comment
        """
        await self.session.flush()
        await self.session.refresh(comment)
        logger.debug(f"Updated comment: {comment.id}")
        return comment

    async def soft_delete(self, comment_id: uuid.UUID) -> bool:
        """
        댓글 소프트 삭제.

        대댓글이 있는 경우에도 구조 유지를 위해 soft delete 사용.

        Args:
            comment_id: 삭제할 댓글 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        comment = await self.get_by_id(comment_id)
        if comment is None:
            return False

        comment.is_deleted = True
        comment.content = "[삭제된 댓글입니다]"  # 내용 마스킹
        await self.session.flush()
        logger.debug(f"Soft deleted comment: {comment_id}")
        return True

    async def count_by_post(self, post_id: uuid.UUID) -> int:
        """
        게시글의 댓글 총 개수.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 댓글 수
        """
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_replies(self, parent_id: uuid.UUID) -> int:
        """
        특정 댓글의 대댓글 수.

        Args:
            parent_id: 부모 댓글 UUID

        Returns:
            int: 대댓글 수
        """
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.parent_id == parent_id, Comment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()