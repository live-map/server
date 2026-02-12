"""
PollComment Service - Business logic for poll comments.

커뮤니티 CommentService와 동일한 패턴.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Sequence

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
    option_id: uuid.UUID | None
    likes: int
    depth: int
    created_at: str
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
            option_id=comment.option_id,
            likes=comment.likes,
            depth=comment.depth,
            created_at=comment.created_at.isoformat(),
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
        # 여론조사 존재 확인
        poll = await self.poll_repo.get_by_id(poll_id)
        if poll is None:
            logger.warning(f"Poll {poll_id} not found for comment creation")
            return None

        depth = 0

        if parent_id is not None:
            parent = await self.comment_repo.get_by_id(parent_id)
            if parent is None:
                logger.warning(f"Parent comment {parent_id} not found")
                return None
            if parent.poll_id != poll_id:
                logger.warning(f"Parent comment {parent_id} belongs to different poll")
                return None
            depth = parent.depth + 1

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
        logger.info(f"Poll comment created: {created.id} on poll {poll_id}")
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
        self, comment_id: uuid.UUID, user_id: str
    ) -> bool:
        """댓글 삭제 (소프트 삭제)."""
        comment = await self.comment_repo.get_by_id(comment_id)
        if comment is None:
            return False
        if comment.user_id != user_id:
            logger.warning(f"User {user_id} tried to delete poll comment {comment_id}")
            return False

        result = await self.comment_repo.soft_delete(comment_id)
        await self.session.commit()
        return result
