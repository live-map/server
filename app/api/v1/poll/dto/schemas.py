"""
Pydantic schemas for Poll API endpoints.

프론트엔드 mock 데이터 타입과 매칭됩니다.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, HttpUrl, Tag


# ========================================
# Option Schemas
# ========================================

class OptionCreate(BaseModel):
    """선택지 생성 요청."""
    text: str = Field(..., min_length=1, max_length=200)
    order: int | None = None


class OptionResponse(BaseModel):
    """선택지 응답."""
    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)

    id: uuid.UUID
    text: str
    order: int = 0
    vote_count: int = Field(alias="voteCount", default=0)


# ========================================
# Source Schemas
# ========================================

class SourceCreate(BaseModel):
    """출처 생성 요청."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    title: str = Field(..., min_length=1, max_length=200)
    url: HttpUrl
    source_type: str = Field(alias="sourceType", default="OTHER")
    description: str | None = None


class SourceResponse(BaseModel):
    """출처 응답."""
    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)

    id: uuid.UUID
    title: str
    url: str
    source_type: str = Field(alias="sourceType")
    description: str | None = None
    created_at: datetime = Field(alias="createdAt")


# ========================================
# Poll Schemas
# ========================================

class PollCreate(BaseModel):
    """여론조사 생성 요청."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    image_url: str | None = Field(None, alias="imageUrl")
    category: str | None = None
    interaction_type: str = Field("SINGLE_CHOICE", alias="interactionType")
    starts_at: datetime | None = Field(None, alias="startsAt")
    ends_at: datetime | None = Field(None, alias="endsAt")
    options: list[OptionCreate] = Field(..., min_length=2, max_length=10)
    sources: list[SourceCreate] | None = None


class PollUpdate(BaseModel):
    """여론조사 수정 요청."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: Literal["ACTIVE", "CLOSED", "DRAFT"] | None = None


class UserBrief(BaseModel):
    """유저 간략 정보."""
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    name: str | None = None
    image: str | None = None


class PollCardResponse(BaseModel):
    """여론조사 카드 응답 (목록용)."""
    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)

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


class PollDetailResponse(PollCardResponse):
    """여론조사 상세 응답."""
    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)

    starts_at: datetime | None = Field(None, alias="startsAt")
    user_id: str = Field(alias="userId")
    updated_at: datetime = Field(alias="updatedAt")
    sources: list[SourceResponse] = []
    comments: list["PollCommentResponse"] = []
    ai_content: str | None = Field(None, alias="aiContent")
    ai_updated_at: datetime | None = Field(None, alias="aiUpdatedAt")
    average_slider_value: float | None = Field(None, alias="averageSliderValue")


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
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    interaction_type: Literal["BINARY", "SINGLE_CHOICE", "EMOJI_REACTION"] = Field(alias="interactionType")
    option_id: uuid.UUID = Field(alias="optionId")


class CastVoteSlider(BaseModel):
    """SLIDER 투표."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    interaction_type: Literal["SLIDER"] = Field(alias="interactionType")
    slider_value: int = Field(alias="sliderValue", ge=0, le=100)


class CastVoteMultiple(BaseModel):
    """MULTIPLE_CHOICE 투표."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    interaction_type: Literal["MULTIPLE_CHOICE"] = Field(alias="interactionType")
    selected_option_ids: list[uuid.UUID] = Field(alias="selectedOptionIds", min_length=1)


class CastVoteRanking(BaseModel):
    """RANKING 투표."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    interaction_type: Literal["RANKING"] = Field(alias="interactionType")
    ranking_data: list[uuid.UUID] = Field(alias="rankingData", min_length=1)


def _vote_discriminator(v: dict) -> str:
    """CastVoteRequest 판별자: interactionType 또는 interaction_type 필드로 분기."""
    if isinstance(v, dict):
        return v.get("interactionType") or v.get("interaction_type", "BINARY")
    return getattr(v, "interaction_type", "BINARY")


CastVoteRequest = Annotated[
    Union[
        Annotated[CastVoteBinary, Tag("BINARY")],
        Annotated[CastVoteBinary, Tag("SINGLE_CHOICE")],
        Annotated[CastVoteBinary, Tag("EMOJI_REACTION")],
        Annotated[CastVoteSlider, Tag("SLIDER")],
        Annotated[CastVoteMultiple, Tag("MULTIPLE_CHOICE")],
        Annotated[CastVoteRanking, Tag("RANKING")],
    ],
    Discriminator(_vote_discriminator),
]


class VoteResponse(BaseModel):
    """투표 응답."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    success: bool
    poll_id: uuid.UUID = Field(alias="pollId")
    vote_data: dict = Field(alias="voteData")


class UserVoteResponse(BaseModel):
    """사용자 투표 현황 응답."""
    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)

    id: uuid.UUID
    option_id: uuid.UUID | None = Field(None, alias="optionId")
    slider_value: int | None = Field(None, alias="sliderValue")
    selected_option_ids: list | None = Field(None, alias="selectedOptionIds")
    ranking_data: list | None = Field(None, alias="rankingData")


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


class HotDebateOption(BaseModel):
    """핫 디베이트 옵션 (multiple/checkbox/ranking 타입용)."""
    id: str
    label: str
    percent: float
    color: str


class HotDebateResponse(BaseModel):
    """핫 디베이트 응답 — 다중 pollType 지원."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: uuid.UUID
    title: str
    poll_type: str = Field(alias="pollType")
    # binary/yesno 전용 (하위호환)
    pro_label: str | None = Field(None, alias="proLabel")
    con_label: str | None = Field(None, alias="conLabel")
    pro_percent: float | None = Field(None, alias="proPercent")
    con_percent: float | None = Field(None, alias="conPercent")
    # 다중 옵션 타입
    options: list[HotDebateOption] | None = None
    # scale 전용
    scale_average: float | None = Field(None, alias="scaleAverage")
    # 공통
    total_votes: int = Field(alias="totalVotes")
    comments: list[HotDebateComment] = []


# ========================================
# Comment Schemas
# ========================================

class PollCommentCreate(BaseModel):
    """여론조사 댓글 생성 요청."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: uuid.UUID | None = Field(None, alias="parentId")
    option_id: uuid.UUID | None = Field(None, alias="optionId")


class PollCommentResponse(BaseModel):
    """여론조사 댓글 응답."""
    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)

    id: uuid.UUID
    poll_id: uuid.UUID = Field(alias="pollId")
    user_id: str = Field(alias="userId")
    user_name: str | None = Field(None, alias="userName")
    user_image: str | None = Field(None, alias="userImage")
    content: str
    option_id: uuid.UUID | None = Field(None, alias="optionId")
    parent_id: uuid.UUID | None = Field(None, alias="parentId")
    likes: int = 0
    depth: int = 0
    created_at: datetime = Field(alias="createdAt")
    is_deleted: bool = Field(False, alias="isDeleted")
    replies: list["PollCommentResponse"] = []


# ========================================
# Research Schemas
# ========================================

class ResearchStatusResponse(BaseModel):
    """리서치 상태 응답."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    status: str = Field(description="pending | running | completed | failed")
    poll_id: uuid.UUID = Field(alias="pollId")
    error: str | None = None
    current_step: str | None = Field(None, alias="currentStep")


class ResearchTriggerResponse(BaseModel):
    """리서치 트리거 응답."""
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    status: str
    poll_id: uuid.UUID = Field(alias="pollId")


# Update forward refs
PollDetailResponse.model_rebuild()
PollCommentResponse.model_rebuild()
