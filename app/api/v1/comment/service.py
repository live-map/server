import logging
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.comment.repository import CommentRepository
from app.models.comment import Comment
from app.api.v1.comment.dto.commentTreeNode import CommentTreeNode
from app.api.v1.post.repository import PostRepository

logger = logging.getLogger(__name__)


class CommentService:
    """
    Comment 관련 비즈니스 로직을 처리하는 서비스.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.comment_repo = CommentRepository(session)
        self.post_repo = PostRepository(session)

    # ========================================
    # Comment Methods
    # ========================================

    async def create_comment(
        self,
        post_id: uuid.UUID,
        user_id: str,
        content: str,
        parent_id: uuid.UUID | None = None,
    ) -> Comment | None:
        """
        댓글/대댓글 작성.

        대댓글의 경우:
        - parent_id가 있으면 해당 댓글의 depth + 1
        - order_number는 부모의 것을 상속

        최상위 댓글의 경우:
        - depth = 0
        - order_number = 새로 할당

        Args:
            post_id: 게시글 UUID
            user_id: 작성자 ID
            content: 내용
            parent_id: 부모 댓글 UUID (대댓글인 경우)

        Returns:
            생성된 Comment 또는 None (게시글/부모 댓글이 없는 경우)
        """
        # 게시글 존재 확인
        post = await self.post_repo.get_by_id(post_id)
        if post is None:
            logger.warning(f"Post {post_id} not found for comment creation")
            return None

        depth = 0
        order_number = 0

        if parent_id is not None:
            # 대댓글: 부모 댓글 확인
            parent = await self.comment_repo.get_by_id(parent_id)
            if parent is None:
                logger.warning(f"Parent comment {parent_id} not found")
                return None

            # 부모 댓글이 같은 게시글에 속하는지 확인
            if parent.post_id != post_id:
                logger.warning(f"Parent comment {parent_id} belongs to different post")
                return None

            depth = parent.depth + 1
            order_number = parent.order_number  # 부모의 그룹에 속함
        else:
            # 최상위 댓글: 새 order_number 할당
            order_number = await self.comment_repo.get_next_order_number(post_id)

        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            parent_id=parent_id,
            content=content,
            depth=depth,
            order_number=order_number,
        )

        created = await self.comment_repo.create(comment)
        await self.session.commit()
        logger.info(
            f"Comment created: {created.id} on post {post_id}, "
            f"parent={parent_id}, depth={depth}"
        )
        return created

    async def get_comments_tree(self, post_id: uuid.UUID) -> list[CommentTreeNode]:
        """
        게시글의 댓글을 트리 구조로 조회.

        플랫 리스트를 트리 구조로 변환하여 반환합니다.

        Args:
            post_id: 게시글 ID

        Returns:
            list[CommentTreeNode]: 최상위 댓글 목록 (각각 replies 포함)
        """
        # 모든 댓글을 플랫하게 조회
        all_comments = await self.comment_repo.get_all_comments_by_post(
            post_id, include_deleted=True  # 삭제된 것도 구조 유지용으로 포함
        )

        # ID -> TreeNode 매핑
        node_map: dict[uuid.UUID, CommentTreeNode] = {}
        root_nodes: list[CommentTreeNode] = []

        # 1단계: 모든 노드 생성
        for comment in all_comments:
            node = CommentTreeNode.from_comment(comment)
            node_map[comment.id] = node

        # 2단계: 트리 구조 구축
        for comment in all_comments:
            node = node_map[comment.id]

            if comment.parent_id is None:
                # 최상위 댓글
                root_nodes.append(node)
            else:
                # 대댓글: 부모 노드에 추가
                parent_node = node_map.get(comment.parent_id)
                if parent_node:
                    parent_node.replies.append(node)

        return root_nodes

    async def get_flat_comments(
        self,
        post_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Comment]:
        """
        게시글의 댓글을 플랫 리스트로 조회.

        depth와 order_number로 정렬되어 있어
        프론트엔드에서 들여쓰기로 표현 가능.

        Args:
            post_id: 게시글 ID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[Comment]: 정렬된 댓글 리스트
        """
        return await self.comment_repo.get_all_comments_by_post(post_id)

    async def update_comment(
        self,
        comment_id: uuid.UUID,
        user_id: str,
        content: str,
    ) -> Comment | None:
        """
        댓글 수정.

        Args:
            comment_id: 댓글 UUID
            user_id: 요청 사용자 ID
            content: 새 내용

        Returns:
            수정된 Comment 또는 None
        """
        comment = await self.comment_repo.get_by_id(comment_id)

        if comment is None:
            return None

        if comment.user_id != user_id:
            logger.warning(f"User {user_id} tried to edit comment {comment_id}")
            return None

        comment.content = content
        updated = await self.comment_repo.update(comment)
        await self.session.commit()
        return updated

    async def delete_comment(self, comment_id: uuid.UUID, user_id: str) -> bool:
        """
        댓글 삭제 (소프트 삭제).

        대댓글이 있어도 구조는 유지됩니다.

        Args:
            comment_id: 댓글 UUID
            user_id: 요청 사용자 ID

        Returns:
            bool: 삭제 성공 여부
        """
        comment = await self.comment_repo.get_by_id(comment_id)

        if comment is None:
            return False

        if comment.user_id != user_id:
            logger.warning(f"User {user_id} tried to delete comment {comment_id}")
            return False

        result = await self.comment_repo.soft_delete(comment_id)
        await self.session.commit()
        return result

    async def get_reply_count(self, comment_id: uuid.UUID) -> int:
        """특정 댓글의 대댓글 수 조회."""
        return await self.comment_repo.count_replies(comment_id)

    async def get_comment_count(self, post_id: uuid.UUID) -> int:
        """게시글의 총 댓글 수 조회."""
        return await self.comment_repo.count_by_post(post_id)