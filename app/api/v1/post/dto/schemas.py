"""
Pydantic schemas for Post, PostMedia, and PostLike API endpoints.
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ========================================
# Media Schemas
# ========================================

class MediaType(str, Enum):
    """미디어 타입."""
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class PostMediaCreate(BaseModel):
    """미디어 생성 요청 (S3 업로드 후)."""
    media_type: MediaType
    url: str = Field(..., max_length=1000)
    thumbnail_url: str | None = Field(None, max_length=1000)
    original_filename: str | None = Field(None, max_length=255)
    file_size: int | None = Field(None, ge=0)
    duration: int | None = Field(None, ge=0, le=60, description="Video duration in seconds (max 60)")
    width: int | None = Field(None, ge=0)
    height: int | None = Field(None, ge=0)
    order: int = Field(0, ge=0)


class PostMediaResponse(BaseModel):
    """미디어 응답."""
    id: uuid.UUID
    post_id: uuid.UUID
    media_type: MediaType
    url: str
    thumbnail_url: str | None = None
    original_filename: str | None = None
    file_size: int | None = None
    duration: int | None = None
    width: int | None = None
    height: int | None = None
    order: int
    created_at: datetime

    class Config:
        from_attributes = True


# ========================================
# Like Schemas
# ========================================

class LikeResponse(BaseModel):
    """좋아요 작업 응답."""
    success: bool
    is_liked: bool
    like_count: int
    message: str


class PostLikerResponse(BaseModel):
    """좋아요한 사용자 정보."""
    user_id: str
    user_name: str | None = None
    user_image: str | None = None
    liked_at: datetime

    class Config:
        from_attributes = True


class PostLikersListResponse(BaseModel):
    """좋아요한 사용자 목록 응답."""
    items: list[PostLikerResponse]
    total: int
    limit: int
    offset: int


# ========================================
# Post Schemas
# ========================================

class PostCreate(BaseModel):
    """게시글 생성 요청."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    media: list[PostMediaCreate] | None = Field(None, description="Optional media attachments")


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
    like_count: int = 0
    is_liked: bool = False  # 현재 사용자의 좋아요 여부
    media: list[PostMediaResponse] = []
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

