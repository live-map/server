"""
PollComment Service - Business logic for poll comments.

커뮤니티 CommentService와 동일한 패턴.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.poll.comment.repository import PollCommentRepository
from app.api.v1.poll.repository import PollRepository
from app.models.poll_comment import PollComment

logger = logging.getLogger(__name__)


@dataclass
class PollCommentTreeNode:
    """댓글 트리 노드."""
    id: uuid.UUID
    poll_id: uuid.UUID
    user_id: str
    user_name: str | None
    user_image: str | None
    content: str
    parent_id: uuid.UUID | None
    option_id: uuid.UUID | None
    likes: int
    depth: int
    created_at: datetime
    is_deleted: bool
    replies: list["PollCommentTreeNode"] = field(default_factory=list)

    @classmethod
    def from_comment(cls, comment: PollComment) -> "PollCommentTreeNode":
        return cls(
            id=comment.id,
            poll_id=comment.poll_id,
            user_id=comment.user_id,
            user_name=comment.user.name if comment.user else None,
            user_image=comment.user.image if comment.user else None,
            content=comment.content if not comment.is_deleted else "삭제된 댓글입니다.",
            parent_id=comment.parent_id,
            option_id=comment.option_id,
            likes=comment.likes,
            depth=comment.depth,
            created_at=comment.created_at,
            is_deleted=comment.is_deleted,
        )


class PollCommentService:
    """PollComment 관련 비즈니스 로직."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.comment_repo = PollCommentRepository(session)
        self.poll_repo = PollRepository(session)

    async def create_comment(
        self,
        poll_id: uuid.UUID,
        user_id: str,
        content: str,
        parent_id: uuid.UUID | None = None,
        option_id: uuid.UUID | None = None,
    ) -> PollComment | None:
        """댓글/대댓글 작성."""
        # 여론조사 존재 확인 (옵션 포함 로드 - option_id 검증용)
        poll = await self.poll_repo.get_by_id_with_details(poll_id)
        if poll is None:
            logger.warning("Poll %s not found for comment creation", poll_id)
            return None

        # option_id가 이 poll의 옵션인지 검증
        if option_id is not None:
            valid_option_ids = {opt.id for opt in poll.options}
            if option_id not in valid_option_ids:
                logger.warning(
                    "Option %s does not belong to poll %s", option_id, poll_id
                )
                raise ValueError("해당 여론조사에 속하지 않는 선택지입니다.")

        depth = 0

        if parent_id is not None:
            parent = await self.comment_repo.get_by_id(parent_id)
            if parent is None:
                logger.warning("Parent comment %s not found", parent_id)
                return None
            if parent.poll_id != poll_id:
                logger.warning("Parent comment %s belongs to different poll", parent_id)
                return None
            depth = parent.depth + 1
            if depth >= 3:
                logger.warning("Comment depth limit exceeded: depth=%d", depth)
                raise ValueError("대댓글은 최대 3단계까지만 허용됩니다.")

        comment = PollComment(
            poll_id=poll_id,
            user_id=user_id,
            parent_id=parent_id,
            option_id=option_id,
            content=content,
            depth=depth,
        )

        created = await self.comment_repo.create(comment)
        await self.session.commit()
        # user 관계 로드 (응답에 userName/userImage 포함)
        await self.session.refresh(created, attribute_names=["user"])
        logger.info("Poll comment created: %s on poll %s", created.id, poll_id)
        return created

    async def get_comments_tree(self, poll_id: uuid.UUID) -> list[PollCommentTreeNode]:
        """여론조사 댓글을 트리 구조로 조회."""
        all_comments = await self.comment_repo.get_all_by_poll(
            poll_id, include_deleted=True
        )

        node_map: dict[uuid.UUID, PollCommentTreeNode] = {}
        root_nodes: list[PollCommentTreeNode] = []

        # 1단계: 모든 노드 생성
        for comment in all_comments:
            node = PollCommentTreeNode.from_comment(comment)
            node_map[comment.id] = node

        # 2단계: 트리 구조 구축
        for comment in all_comments:
            node = node_map[comment.id]
            if comment.parent_id is None:
                root_nodes.append(node)
            else:
                parent_node = node_map.get(comment.parent_id)
                if parent_node:
                    parent_node.replies.append(node)

        return root_nodes

    async def delete_comment(
        self, comment_id: uuid.UUID, user_id: str, poll_id: uuid.UUID | None = None,
    ) -> bool:
        """댓글 삭제 (소프트 삭제)."""
        comment = await self.comment_repo.get_by_id(comment_id)
        if comment is None:
            return False
        if comment.user_id != user_id:
            logger.warning("User %s tried to delete poll comment %s", user_id, comment_id)
            return False
        # poll_id 검증: URL의 poll_id와 댓글의 poll_id 일치 확인
        if poll_id is not None and comment.poll_id != poll_id:
            return False

        result = await self.comment_repo.soft_delete(comment)
        await self.session.commit()
        return result

    async def like_comment(
        self, comment_id: uuid.UUID, user_id: str, poll_id: uuid.UUID | None = None,
    ) -> dict | None:
        """댓글 좋아요 토글 (원자적 증가 방식)."""
        comment = await self.comment_repo.get_by_id(comment_id)
        if comment is None:
            return None

        # poll_id 검증: URL의 poll_id와 댓글의 poll_id 일치 확인
        if poll_id is not None and comment.poll_id != poll_id:
            return None

        stmt = (
            update(PollComment)
            .where(PollComment.id == comment_id)
            .values(likes=PollComment.likes + 1)
            .returning(PollComment.likes)
        )
        result = await self.session.execute(stmt)
        new_likes = result.scalar_one()
        await self.session.commit()
        logger.info("Poll comment %s liked by %s", comment_id, user_id)
        return {"likes": new_likes}
