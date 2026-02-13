"""
Pydantic schemas for Poll API endpoints.

프론트엔드 mock 데이터 타입과 매칭됩니다.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ========================================
# Option Schemas
# ========================================

class OptionCreate(BaseModel):
    """선택지 생성 요청."""
    text: str = Field(..., min_length=1, max_length=200)
    order: int | None = None


class OptionResponse(BaseModel):
    """선택지 응답."""
    id: uuid.UUID
    text: str
    vote_count: int = Field(alias="voteCount", default=0)

    class Config:
        from_attributes = True
        populate_by_name = True


# ========================================
# Source Schemas
# ========================================

class SourceCreate(BaseModel):
    """출처 생성 요청."""
    title: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1)
    source_type: str = Field(alias="sourceType", default="OTHER")
    description: str | None = None

    class Config:
        populate_by_name = True


class SourceResponse(BaseModel):
    """출처 응답."""
    id: uuid.UUID
    title: str
    url: str
    source_type: str = Field(alias="sourceType")
    description: str | None = None
    created_at: datetime = Field(alias="createdAt")

    class Config:
        from_attributes = True
        populate_by_name = True


# ========================================
# Poll Schemas
# ========================================

class PollCreate(BaseModel):
    """여론조사 생성 요청."""
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    image_url: str | None = Field(None, alias="imageUrl")
    category: str | None = None
    interaction_type: str = Field("SINGLE_CHOICE", alias="interactionType")
    starts_at: datetime | None = Field(None, alias="startsAt")
    ends_at: datetime | None = Field(None, alias="endsAt")
    options: list[OptionCreate] = Field(..., min_length=2, max_length=10)
    sources: list[SourceCreate] | None = None

    class Config:
        populate_by_name = True


class PollUpdate(BaseModel):
    """여론조사 수정 요청."""
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None

    class Config:
        populate_by_name = True


class UserBrief(BaseModel):
    """유저 간략 정보."""
    id: str | None = None
    name: str | None = None
    image: str | None = None

    class Config:
        from_attributes = True


class PollCardResponse(BaseModel):
    """여론조사 카드 응답 (목록용)."""
    id: uuid.UUID
    title: str
    description: str | None = None
    image_url: str | None = Field(None, alias="imageUrl")
    category: str | None = None
    type: str
    status: str
    interaction_type: str = Field(alias="interactionType")
    total_votes: int = Field(alias="totalVotes", default=0)
    view_count: int = Field(alias="viewCount", default=0)
    created_at: datetime = Field(alias="createdAt")
    ends_at: datetime | None = Field(None, alias="endsAt")
    options: list[OptionResponse] = []
    user: UserBrief | None = None

    class Config:
        from_attributes = True
        populate_by_name = True


class PollDetailResponse(PollCardResponse):
    """여론조사 상세 응답."""
    starts_at: datetime | None = Field(None, alias="startsAt")
    user_id: str = Field(alias="userId")
    updated_at: datetime = Field(alias="updatedAt")
    sources: list[SourceResponse] = []
    comments: list["PollCommentResponse"] = []
    ai_content: str | None = Field(None, alias="aiContent")
    ai_updated_at: datetime | None = Field(None, alias="aiUpdatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


class PollListResponse(BaseModel):
    """여론조사 목록 응답."""
    items: list[PollCardResponse]
    total: int
    limit: int
    offset: int


# ========================================
# Vote Schemas
# ========================================

class CastVoteBinary(BaseModel):
    """BINARY / SINGLE_CHOICE / EMOJI_REACTION 투표."""
    interaction_type: Literal["BINARY", "SINGLE_CHOICE", "EMOJI_REACTION"] = Field(alias="interactionType")
    option_id: uuid.UUID = Field(alias="optionId")

    class Config:
        populate_by_name = True


class CastVoteSlider(BaseModel):
    """SLIDER 투표."""
    interaction_type: Literal["SLIDER"] = Field(alias="interactionType")
    slider_value: int = Field(alias="sliderValue", ge=0, le=100)

    class Config:
        populate_by_name = True


class CastVoteMultiple(BaseModel):
    """MULTIPLE_CHOICE 투표."""
    interaction_type: Literal["MULTIPLE_CHOICE"] = Field(alias="interactionType")
    selected_option_ids: list[uuid.UUID] = Field(alias="selectedOptionIds", min_length=1)

    class Config:
        populate_by_name = True


class CastVoteRanking(BaseModel):
    """RANKING 투표."""
    interaction_type: Literal["RANKING"] = Field(alias="interactionType")
    ranking_data: list[uuid.UUID] = Field(alias="rankingData", min_length=1)

    class Config:
        populate_by_name = True


CastVoteRequest = CastVoteBinary | CastVoteSlider | CastVoteMultiple | CastVoteRanking


class VoteResponse(BaseModel):
    """투표 응답."""
    success: bool
    poll_id: uuid.UUID = Field(alias="pollId")
    vote_data: dict = Field(alias="voteData")

    class Config:
        populate_by_name = True


class UserVoteResponse(BaseModel):
    """사용자 투표 현황 응답."""
    id: uuid.UUID
    option_id: uuid.UUID | None = Field(None, alias="optionId")
    slider_value: int | None = Field(None, alias="sliderValue")
    selected_option_ids: list | None = Field(None, alias="selectedOptionIds")
    ranking_data: list | None = Field(None, alias="rankingData")

    class Config:
        from_attributes = True
        populate_by_name = True


# ========================================
# Hot Debate Schemas
# ========================================

class HotDebateComment(BaseModel):
    """핫 디베이트 댓글."""
    id: uuid.UUID
    author: str
    content: str
    side: str
    likes: int


class HotDebateResponse(BaseModel):
    """핫 디베이트 응답."""
    id: uuid.UUID
    title: str
    pro_label: str = Field(alias="proLabel")
    con_label: str = Field(alias="conLabel")
    pro_percent: float = Field(alias="proPercent")
    con_percent: float = Field(alias="conPercent")
    total_votes: int = Field(alias="totalVotes")
    comments: list[HotDebateComment] = []

    class Config:
        populate_by_name = True


# ========================================
# Comment Schemas
# ========================================

class PollCommentCreate(BaseModel):
    """여론조사 댓글 생성 요청."""
    content: str = Field(..., min_length=1)
    parent_id: uuid.UUID | None = Field(None, alias="parentId")
    option_id: uuid.UUID | None = Field(None, alias="optionId")

    class Config:
        populate_by_name = True


class PollCommentResponse(BaseModel):
    """여론조사 댓글 응답."""
    id: uuid.UUID
    poll_id: uuid.UUID = Field(alias="pollId")
    user_id: str = Field(alias="userId")
    user_name: str | None = Field(None, alias="userName")
    user_image: str | None = Field(None, alias="userImage")
    content: str
    option_id: uuid.UUID | None = Field(None, alias="optionId")
    likes: int = 0
    depth: int = 0
    created_at: datetime = Field(alias="createdAt")
    is_deleted: bool = Field(False, alias="isDeleted")
    replies: list["PollCommentResponse"] = []

    class Config:
        from_attributes = True
        populate_by_name = True


# ========================================
# Research Schemas
# ========================================

class ResearchStatusResponse(BaseModel):
    """리서치 상태 응답."""
    status: str = Field(description="pending | running | completed | failed")
    poll_id: uuid.UUID = Field(alias="pollId")
    error: str | None = None

    class Config:
        populate_by_name = True


class ResearchTriggerResponse(BaseModel):
    """리서치 트리거 응답."""
    status: str
    poll_id: uuid.UUID = Field(alias="pollId")

    class Config:
        populate_by_name = True


# Update forward refs
PollDetailResponse.model_rebuild()
PollCommentResponse.model_rebuild()
