from dataclasses import dataclass
import uuid

from app.models.comment import Comment

@dataclass 
class CommentTreeNode:
    """
    댓글 트리 노드 DTO.

    계층 구조를 클라이언트에 전달하기 위한 형태.
    """
    id: uuid.UUID
    user_id: str
    user_name: str | None
    content: str
    depth: int
    created_at: str
    is_deleted: bool
    replies: list["CommentTreeNode"]

    @classmethod
    def from_comment(cls, comment: Comment) -> "CommentTreeNode":
        """Comment 엔티티를 트리 노드로 변환."""
        return cls(
            id=comment.id,
            user_id=comment.user_id,
            user_name=comment.user.name if comment.user else None,
            content=comment.content if not comment.is_deleted else "[삭제된 댓글입니다]",
            depth=comment.depth,
            created_at=comment.created_at.isoformat(),
            is_deleted=comment.is_deleted,
            replies=[],  # 나중에 채워짐
        )
