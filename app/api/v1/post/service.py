"""
Post Service - Business logic for posts and comments.

Orchestrates operations between controller and repository layers.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.post.repository import PostRepository
from app.models.post import Post

logger = logging.getLogger(__name__)


# ========================================
# Custom Exceptions (Domain Layer)
# ========================================

class PostNotFoundError(Exception):
    """Raised when a post is not found."""
    pass


class PostPermissionError(Exception):
    """Raised when user doesn't have permission to modify a post."""
    pass


class PostService:
    """
    Post 관련 비즈니스 로직을 처리하는 서비스.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.post_repo = PostRepository(session)

    # ========================================
    # Post Methods
    # ========================================

    async def create_post(self, user_id: str, title: str, content: str) -> Post:
        """
        새 게시글 작성 (commit 포함).

        미디어 없이 게시글만 생성할 때 사용합니다.

        Args:
            user_id: 작성자 ID
            title: 제목
            content: 내용

        Returns:
            생성된 Post
        """
        post = await self.create_post_without_commit(user_id, title, content)
        await self.session.commit()
        logger.info(f"Post created: {post.id} by user {user_id}")
        return post

    async def create_post_without_commit(self, user_id: str, title: str, content: str) -> Post:
        """
        새 게시글 작성 (commit 없음 - 트랜잭션 유지).

        미디어와 함께 게시글을 생성할 때 사용합니다.
        호출자가 commit을 담당합니다.

        Args:
            user_id: 작성자 ID
            title: 제목
            content: 내용

        Returns:
            생성된 Post (아직 commit되지 않음)
        """
        post = Post(
            user_id=user_id,
            title=title,
            content=content,
        )
        created = await self.post_repo.create(post)
        logger.debug(f"Post created (uncommitted): {created.id} by user {user_id}")
        return created

    async def get_post(self, post_id: uuid.UUID) -> Post | None:
        """게시글 단건 조회."""
        return await self.post_repo.get_by_id(post_id)

    async def get_post_with_comments(self, post_id: uuid.UUID) -> Post | None:
        """게시글 + 댓글 조회."""
        return await self.post_repo.get_by_id_with_comments(post_id)

    async def list_posts(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: str | None = None,
    ) -> Sequence[Post]:
        """게시글 목록 조회."""
        return await self.post_repo.get_all(limit=limit, offset=offset, user_id=user_id)

    async def update_post(
        self,
        post_id: uuid.UUID,
        user_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> Post:
        """
        게시글 수정.

        Args:
            post_id: 게시글 UUID
            user_id: 요청한 사용자 ID (권한 확인용)
            title: 새 제목 (선택)
            content: 새 내용 (선택)

        Returns:
            수정된 Post

        Raises:
            PostNotFoundError: 게시글이 존재하지 않을 때
            PostPermissionError: 권한이 없을 때
        """
        post = await self.post_repo.get_by_id(post_id)

        if post is None:
            raise PostNotFoundError(f"Post with id {post_id} not found")

        # 권한 확인: 작성자만 수정 가능
        if post.user_id != user_id:
            logger.warning(f"User {user_id} tried to edit post {post_id} owned by {post.user_id}")
            raise PostPermissionError(f"User {user_id} is not the owner of post {post_id}")

        if title is not None:
            post.title = title
        if content is not None:
            post.content = content

        updated = await self.post_repo.update(post)
        await self.session.commit()
        return updated

    async def delete_post(self, post_id: uuid.UUID, user_id: str) -> bool:
        """
        게시글 삭제.

        Args:
            post_id: 게시글 UUID
            user_id: 요청한 사용자 ID

        Returns:
            bool: 삭제 성공 여부

        Raises:
            PostNotFoundError: 게시글이 존재하지 않을 때
            PostPermissionError: 권한이 없을 때
        """
        post = await self.post_repo.get_by_id(post_id)

        if post is None:
            raise PostNotFoundError(f"Post with id {post_id} not found")

        if post.user_id != user_id:
            logger.warning(f"User {user_id} tried to delete post {post_id}")
            raise PostPermissionError(f"User {user_id} is not the owner of post {post_id}")

        result = await self.post_repo.soft_delete(post_id)
        await self.session.commit()
        return result
