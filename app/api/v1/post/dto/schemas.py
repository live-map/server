"""
Pydantic schemas for Post and Comment API endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ========================================
# Post Schemas
# ========================================

class PostCreate(BaseModel):
    """게시글 생성 요청."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class PostUpdate(BaseModel):
    """게시글 수정 요청."""
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)


class PostResponse(BaseModel):
    """게시글 응답."""
    id: uuid.UUID
    user_id: str
    user_name: str | None = None
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    comment_count: int = 0

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    """게시글 목록 응답."""
    items: list[PostResponse]
    total: int
    limit: int
    offset: int

