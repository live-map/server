"""
PostLike Service - Business logic for post likes.

Handles like/unlike operations with like_count synchronization.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.post.like.repository import PostLikeRepository
from app.api.v1.post.sort import compute_popularity_score
from app.models.post import Post
from app.models.post_like import PostLike

logger = logging.getLogger(__name__)


# ========================================
# Custom Exceptions
# ========================================

class PostNotFoundForLikeError(Exception):
    """Raised when trying to like a post that doesn't exist or is deleted."""
    pass


@dataclass
class LikeResult:
    """좋아요 작업 결과."""
    success: bool
    is_liked: bool
    like_count: int
    message: str


class PostLikeService:
    """
    PostLike 관련 비즈니스 로직을 처리하는 서비스.

    좋아요/취소와 like_count 동기화를 담당합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.like_repo = PostLikeRepository(session)

    async def _recalculate_popularity(self, post_id: uuid.UUID) -> None:
        """좋아요 변경 후 인기도 점수 재계산."""
        from sqlalchemy import select
        stmt = select(Post).where(Post.id == post_id)
        result = await self.session.execute(stmt)
        post = result.scalar_one_or_none()
        if post:
            post.popularity_score = compute_popularity_score(
                likes=post.like_count,
                comments=post.comment_count,
                views=post.view_count,
                created_at=post.created_at,
            )
            await self.session.flush()

    async def like_post(self, post_id: uuid.UUID, user_id: str) -> LikeResult:
        """
        게시글 좋아요.

        이미 좋아요한 경우 실패를 반환합니다.
        게시글이 삭제된 경우 예외를 발생시킵니다.

        Args:
            post_id: 게시글 UUID
            user_id: 사용자 ID

        Returns:
            LikeResult: 작업 결과

        Raises:
            PostNotFoundForLikeError: 게시글이 존재하지 않거나 삭제됨
        """
        # 게시글 존재 및 삭제 상태 확인 (race condition 방지)
        post_exists = await self.like_repo.check_post_exists_and_active(post_id)
        if not post_exists:
            raise PostNotFoundForLikeError(f"Post {post_id} not found or deleted")

        # 이미 좋아요했는지 확인
        already_liked = await self.like_repo.exists(post_id, user_id)
        if already_liked:
            like_count = await self.like_repo.count_by_post_id(post_id)
            return LikeResult(
                success=False,
                is_liked=True,
                like_count=like_count,
                message="Already liked this post",
            )

        # 좋아요 생성
        like = PostLike(post_id=post_id, user_id=user_id)
        await self.like_repo.create(like)

        # like_count 증가 (실패 시 전체 트랜잭션 롤백됨)
        updated = await self.like_repo.increment_like_count(post_id)
        if not updated:
            # like_count 업데이트 실패 = 게시글이 삭제됨 (race condition)
            await self.session.rollback()
            raise PostNotFoundForLikeError(f"Post {post_id} was deleted during like operation")

        await self._recalculate_popularity(post_id)
        await self.session.commit()

        like_count = await self.like_repo.count_by_post_id(post_id)
        logger.info(f"User {user_id} liked post {post_id}")

        return LikeResult(
            success=True,
            is_liked=True,
            like_count=like_count,
            message="Post liked successfully",
        )

    async def unlike_post(self, post_id: uuid.UUID, user_id: str) -> LikeResult:
        """
        게시글 좋아요 취소.

        좋아요하지 않은 경우 실패를 반환합니다.

        Args:
            post_id: 게시글 UUID
            user_id: 사용자 ID

        Returns:
            LikeResult: 작업 결과
        """
        # 좋아요 존재 확인
        is_liked = await self.like_repo.exists(post_id, user_id)
        if not is_liked:
            like_count = await self.like_repo.count_by_post_id(post_id)
            return LikeResult(
                success=False,
                is_liked=False,
                like_count=like_count,
                message="Not liked this post",
            )

        # like_count 감소 먼저 (실패하면 삭제도 하지 않음)
        updated = await self.like_repo.decrement_like_count(post_id)

        # 좋아요 삭제 (like_count 감소 성공한 경우만)
        if updated:
            await self.like_repo.delete(post_id, user_id)
        else:
            # like_count가 이미 0이면 desync 상태 - 삭제만 수행
            logger.warning(f"like_count desync detected for post {post_id}, deleting like anyway")
            await self.like_repo.delete(post_id, user_id)

        await self._recalculate_popularity(post_id)
        await self.session.commit()

        like_count = await self.like_repo.count_by_post_id(post_id)
        logger.info(f"User {user_id} unliked post {post_id}")

        return LikeResult(
            success=True,
            is_liked=False,
            like_count=like_count,
            message="Post unliked successfully",
        )

    async def toggle_like(self, post_id: uuid.UUID, user_id: str) -> LikeResult:
        """
        게시글 좋아요 토글.

        좋아요 상태에 따라 자동으로 좋아요/취소를 수행합니다.

        Args:
            post_id: 게시글 UUID
            user_id: 사용자 ID

        Returns:
            LikeResult: 작업 결과
        """
        is_liked = await self.like_repo.exists(post_id, user_id)

        if is_liked:
            return await self.unlike_post(post_id, user_id)
        else:
            return await self.like_post(post_id, user_id)

    async def is_liked_by_user(self, post_id: uuid.UUID, user_id: str) -> bool:
        """
        사용자의 좋아요 여부 확인.

        Args:
            post_id: 게시글 UUID
            user_id: 사용자 ID

        Returns:
            bool: 좋아요 여부
        """
        return await self.like_repo.exists(post_id, user_id)

    async def get_like_count(self, post_id: uuid.UUID) -> int:
        """
        게시글의 좋아요 수.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 좋아요 수
        """
        return await self.like_repo.count_by_post_id(post_id)

    async def get_post_likers(
        self,
        post_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[PostLike]:
        """
        게시글을 좋아요한 사용자 목록.

        Args:
            post_id: 게시글 UUID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[PostLike]: 좋아요 목록 (최신순)
        """
        return await self.like_repo.get_by_post_id(post_id, limit, offset)

    async def get_user_liked_posts(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[PostLike]:
        """
        사용자가 좋아요한 게시글 목록.

        Args:
            user_id: 사용자 ID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[PostLike]: 좋아요 목록 (최신순)
        """
        return await self.like_repo.get_user_liked_posts(user_id, limit, offset)

    async def get_like_status_for_posts(
        self,
        post_ids: list[uuid.UUID],
        user_id: str,
    ) -> dict[uuid.UUID, bool]:
        """
        여러 게시글에 대한 좋아요 상태 일괄 조회.

        게시글 목록 API에서 N+1 쿼리를 방지하기 위해 사용합니다.

        Args:
            post_ids: 게시글 UUID 목록
            user_id: 사용자 ID

        Returns:
            dict[UUID, bool]: {post_id: is_liked}
        """
        return await self.like_repo.get_like_status_for_posts(post_ids, user_id)
