"""
Pydantic schemas for Comment API endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    """댓글 생성 요청 (독립된 /comments 엔드포인트용)."""
    post_id: uuid.UUID = Field(..., description="게시글 UUID")
    content: str = Field(..., min_length=1, max_length=1000)
    parent_id: uuid.UUID | None = Field(None, description="대댓글인 경우 부모 댓글 UUID")


class CommentUpdate(BaseModel):
    """댓글 수정 요청."""
    content: str = Field(..., min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    """댓글 단일 응답."""
    id: uuid.UUID
    post_id: uuid.UUID
    user_id: str
    user_name: str | None = None
    parent_id: uuid.UUID | None
    content: str
    depth: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    reply_count: int = 0

    class Config:
        from_attributes = True


class CommentTreeResponse(BaseModel):
    """댓글 트리 노드 응답 (재귀 구조)."""
    id: uuid.UUID
    user_id: str
    user_name: str | None
    content: str
    depth: int
    created_at: str
    is_deleted: bool
    replies: list["CommentTreeResponse"] = []

    class Config:
        from_attributes = True


# Forward reference 해결
CommentTreeResponse.model_rebuild()


class CommentListResponse(BaseModel):
    """댓글 목록 응답 (플랫)."""
    items: list[CommentResponse]
    total: int


class CommentTreeListResponse(BaseModel):
    """댓글 트리 목록 응답."""
    items: list[CommentTreeResponse]
    total: int