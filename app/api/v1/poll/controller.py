"""
Poll Controller - API route handlers for poll endpoints.

여론조사 CRUD, 투표, 댓글, 핫 디베이트 API를 제공합니다.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.interpreter import CurrentAdmin, CurrentUser, CurrentUserOptional
from app.api.v1.poll.dto.schemas import (
    CastVoteBinary,
    CastVoteMultiple,
    CastVoteRanking,
    CastVoteRequest,
    CastVoteSlider,
    HotDebateComment,
    HotDebateOption,
    HotDebateResponse,
    OptionResponse,
    PollCardResponse,
    PollCommentCreate,
    PollCommentResponse,
    PollCreate,
    PollDetailResponse,
    PollListResponse,
    PollUpdate,
    ResearchStatusResponse,
    ResearchTriggerResponse,
    SourceResponse,
    UserBrief,
    UserVoteResponse,
    VoteResponse,
)
from app.api.v1.poll.service import PollService, PollNotFoundError, PollPermissionError
from app.api.v1.poll.vote.service import (
    VoteService,
    AlreadyVotedError,
    InvalidOptionError,
    PollNotActiveError,
)
from app.api.v1.poll.comment.service import PollCommentService
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/polls", tags=["polls"])


# ========================================
# Dependencies
# ========================================

async def get_poll_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PollService:
    return PollService(session)


async def get_vote_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VoteService:
    return VoteService(session)


async def get_comment_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PollCommentService:
    return PollCommentService(session)


PollServiceDep = Annotated[PollService, Depends(get_poll_service)]
VoteServiceDep = Annotated[VoteService, Depends(get_vote_service)]
CommentServiceDep = Annotated[PollCommentService, Depends(get_comment_service)]


# ========================================
# Helper: model → response
# ========================================

def _poll_to_card(poll) -> PollCardResponse:
    return PollCardResponse(
        id=poll.id,
        title=poll.title,
        description=poll.description,
        imageUrl=poll.image_url,
        category=poll.category,
        type=poll.type,
        status=poll.status,
        interactionType=poll.interaction_type,
        totalVotes=poll.total_votes,
        viewCount=poll.view_count,
        createdAt=poll.created_at,
        endsAt=poll.ends_at,
        options=[
            OptionResponse(id=o.id, text=o.text, voteCount=o.vote_count)
            for o in (poll.options or [])
        ],
        user=UserBrief(
            id=poll.user.id if poll.user else None,
            name=poll.user.name if poll.user else None,
            image=poll.user.image if poll.user else None,
        ) if poll.user else None,
    )


def _poll_to_detail(poll) -> PollDetailResponse:
    return PollDetailResponse(
        id=poll.id,
        title=poll.title,
        description=poll.description,
        imageUrl=poll.image_url,
        category=poll.category,
        type=poll.type,
        status=poll.status,
        interactionType=poll.interaction_type,
        totalVotes=poll.total_votes,
        viewCount=poll.view_count,
        createdAt=poll.created_at,
        endsAt=poll.ends_at,
        startsAt=poll.starts_at,
        userId=poll.user_id,
        updatedAt=poll.updated_at,
        aiContent=poll.ai_content,
        aiUpdatedAt=poll.ai_updated_at,
        options=[
            OptionResponse(id=o.id, text=o.text, voteCount=o.vote_count)
            for o in (poll.options or [])
        ],
        sources=[
            SourceResponse(
                id=s.id, title=s.title, url=s.url,
                sourceType=s.source_type, description=s.description,
                createdAt=s.created_at,
            )
            for s in (poll.sources or [])
        ],
        comments=[
            PollCommentResponse(
                id=c.id, pollId=c.poll_id, userId=c.user_id,
                userName=c.user.name if c.user else None,
                userImage=c.user.image if c.user else None,
                content=c.content if not c.is_deleted else "삭제된 댓글입니다.",
                optionId=c.option_id, likes=c.likes, depth=c.depth,
                createdAt=c.created_at, isDeleted=c.is_deleted,
            )
            for c in (poll.comments or []) if c.parent_id is None
        ],
        user=UserBrief(
            id=poll.user.id if poll.user else None,
            name=poll.user.name if poll.user else None,
            image=poll.user.image if poll.user else None,
        ) if poll.user else None,
    )


# ========================================
# Poll Endpoints
# ========================================

@router.post(
    "",
    response_model=PollDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="여론조사 생성 (제안)",
)
async def create_poll(
    data: PollCreate,
    current_user: CurrentUser,
    service: PollServiceDep,
) -> PollDetailResponse:
    """새 여론조사를 생성합니다. 인증 필요."""
    poll = await service.create_poll(
        user_id=current_user.user_id,
        title=data.title,
        description=data.description,
        image_url=data.image_url,
        category=data.category,
        interaction_type=data.interaction_type,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        options=[{"text": o.text, "order": o.order} for o in data.options],
        sources=[
            {
                "title": s.title, "url": s.url,
                "source_type": s.source_type, "description": s.description,
            }
            for s in data.sources
        ] if data.sources else None,
    )
    return _poll_to_detail(poll)


@router.get(
    "",
    response_model=PollListResponse,
    summary="여론조사 목록 조회",
)
async def list_polls(
    service: PollServiceDep,
    current_user: CurrentUserOptional = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[str, Query(description="popular, recent, ending_soon, closed")] = "popular",
    search: Annotated[str | None, Query()] = None,
) -> PollListResponse:
    """여론조사 목록을 조회합니다."""
    polls = await service.list_polls(limit=limit, offset=offset, sort=sort, search=search)
    total = await service.count_polls(search=search)

    return PollListResponse(
        items=[_poll_to_card(p) for p in polls],
        total=total,
        limit=limit,
        offset=offset,
    )


# interaction_type → pollType 매핑
_INTERACTION_TO_POLL_TYPE: dict[str, str] = {
    "BINARY": "binary",
    "SINGLE_CHOICE": "multiple",
    "MULTIPLE_CHOICE": "checkbox",
    "SLIDER": "scale",
    "RANKING": "ranking",
}

# 옵션 색상 팔레트 (프론트엔드 hot-debate.tsx와 매칭)
_OPTION_COLORS = ["#3B82F6", "#EF4444", "#F59E0B", "#10B981", "#8B5CF6"]


@router.get(
    "/hot-debate",
    response_model=HotDebateResponse | None,
    summary="핫 디베이트 조회",
)
async def get_hot_debate(
    service: PollServiceDep,
) -> HotDebateResponse | None:
    """가장 접전인 여론조사를 조회합니다 (모든 타입 지원)."""
    poll = await service.get_hot_debate()
    if poll is None:
        return None

    if len(poll.options) < 2:
        return None

    total = poll.total_votes or 1
    poll_type = _INTERACTION_TO_POLL_TYPE.get(poll.interaction_type, "multiple")

    # 댓글 구성
    comments: list[HotDebateComment] = []
    first_opt_id = poll.options[0].id if poll.options else None
    for c in (poll.comments or [])[:10]:
        side = "pro" if c.option_id == first_opt_id else "con"
        comments.append(HotDebateComment(
            id=c.id,
            author=c.user.name if c.user else "익명",
            content=c.content,
            side=side,
            likes=c.likes,
        ))

    # binary 타입: 상위 2개 옵션으로 pro/con 구성
    if poll_type == "binary" and len(poll.options) == 2:
        opt_a, opt_b = poll.options[0], poll.options[1]
        pro_pct = round((opt_a.vote_count / total) * 1000) / 10
        con_pct = round((opt_b.vote_count / total) * 1000) / 10
        return HotDebateResponse(
            id=poll.id,
            title=poll.title,
            pollType=poll_type,
            proLabel=opt_a.text,
            conLabel=opt_b.text,
            proPercent=pro_pct,
            conPercent=con_pct,
            totalVotes=poll.total_votes,
            comments=comments,
        )

    # 다중 옵션 타입: 모든 옵션의 비율 계산 (합 = 100%)
    sorted_opts = sorted(poll.options, key=lambda o: o.vote_count, reverse=True)
    options = [
        HotDebateOption(
            id=str(opt.id),
            label=opt.text,
            percent=round((opt.vote_count / total) * 1000) / 10,
            color=_OPTION_COLORS[i % len(_OPTION_COLORS)],
        )
        for i, opt in enumerate(sorted_opts)
    ]

    return HotDebateResponse(
        id=poll.id,
        title=poll.title,
        pollType=poll_type,
        options=options,
        totalVotes=poll.total_votes,
        comments=comments,
    )


@router.get(
    "/suggested",
    response_model=list[PollCardResponse],
    summary="유저 제안 목록",
)
async def get_suggested_polls(
    service: PollServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[PollCardResponse]:
    """유저가 제안한 여론조사 목록을 조회합니다."""
    polls = await service.get_suggested_polls(limit)
    return [_poll_to_card(p) for p in polls]


@router.get(
    "/{poll_id}",
    response_model=PollDetailResponse,
    summary="여론조사 상세 조회",
)
async def get_poll(
    poll_id: uuid.UUID,
    service: PollServiceDep,
    current_user: CurrentUserOptional = None,
) -> PollDetailResponse:
    """여론조사 상세 정보를 조회합니다."""
    poll = await service.get_poll_with_details(poll_id)
    if poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")
    return _poll_to_detail(poll)


@router.patch(
    "/{poll_id}",
    response_model=PollCardResponse,
    summary="여론조사 수정",
)
async def update_poll(
    poll_id: uuid.UUID,
    data: PollUpdate,
    current_user: CurrentUser,
    service: PollServiceDep,
) -> PollCardResponse:
    """여론조사를 수정합니다. 작성자만 가능."""
    try:
        poll = await service.update_poll(
            poll_id=poll_id,
            user_id=current_user.user_id,
            title=data.title,
            description=data.description,
            status=data.status,
        )
    except PollNotFoundError:
        raise HTTPException(status_code=404, detail="Poll not found")
    except PollPermissionError:
        raise HTTPException(status_code=403, detail="You are not the owner")

    return PollCardResponse(
        id=poll.id, title=poll.title, description=poll.description,
        imageUrl=poll.image_url, category=poll.category,
        type=poll.type, status=poll.status,
        interactionType=poll.interaction_type,
        totalVotes=poll.total_votes, viewCount=poll.view_count,
        createdAt=poll.created_at, endsAt=poll.ends_at,
    )


@router.delete(
    "/{poll_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="여론조사 삭제",
)
async def delete_poll(
    poll_id: uuid.UUID,
    current_user: CurrentUser,
    service: PollServiceDep,
) -> None:
    """여론조사를 삭제합니다. 작성자만 가능."""
    try:
        await service.delete_poll(poll_id=poll_id, user_id=current_user.user_id)
    except PollNotFoundError:
        raise HTTPException(status_code=404, detail="Poll not found")
    except PollPermissionError:
        raise HTTPException(status_code=403, detail="You are not the owner")


# ========================================
# Vote Endpoints
# ========================================

@router.post(
    "/{poll_id}/vote",
    response_model=VoteResponse,
    summary="투표하기",
)
async def cast_vote(
    poll_id: uuid.UUID,
    data: CastVoteRequest,
    current_user: CurrentUser,
    service: VoteServiceDep,
) -> VoteResponse:
    """여론조사에 투표합니다. 인증 필요."""
    try:
        # Discriminated union에서 필드 추출
        kwargs = {"interaction_type": data.interaction_type}
        if isinstance(data, CastVoteBinary):
            kwargs["option_id"] = data.option_id
        elif isinstance(data, CastVoteSlider):
            kwargs["slider_value"] = data.slider_value
        elif isinstance(data, CastVoteMultiple):
            kwargs["selected_option_ids"] = data.selected_option_ids
        elif isinstance(data, CastVoteRanking):
            kwargs["ranking_data"] = data.ranking_data

        vote = await service.cast_vote(
            user_id=current_user.user_id,
            poll_id=poll_id,
            **kwargs,
        )
    except PollNotActiveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AlreadyVotedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidOptionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PollNotFoundError:
        raise HTTPException(status_code=404, detail="Poll not found")

    return VoteResponse(
        success=True,
        pollId=poll_id,
        voteData={
            "id": str(vote.id),
            "optionId": str(vote.option_id) if vote.option_id else None,
            "sliderValue": vote.slider_value,
            "selectedOptionIds": vote.selected_option_ids,
            "rankingData": vote.ranking_data,
        },
    )


@router.get(
    "/{poll_id}/vote",
    response_model=UserVoteResponse | None,
    summary="내 투표 조회",
)
async def get_user_vote(
    poll_id: uuid.UUID,
    current_user: CurrentUser,
    service: VoteServiceDep,
) -> UserVoteResponse | None:
    """현재 사용자의 투표를 조회합니다."""
    vote = await service.get_user_vote(current_user.user_id, poll_id)
    if vote is None:
        return None
    return UserVoteResponse(
        id=vote.id,
        optionId=vote.option_id,
        sliderValue=vote.slider_value,
        selectedOptionIds=vote.selected_option_ids,
        rankingData=vote.ranking_data,
    )


# ========================================
# Comment Endpoints
# ========================================

@router.post(
    "/{poll_id}/comments",
    response_model=PollCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글 작성",
)
async def create_comment(
    poll_id: uuid.UUID,
    data: PollCommentCreate,
    current_user: CurrentUser,
    service: CommentServiceDep,
) -> PollCommentResponse:
    """여론조사에 댓글을 작성합니다."""
    comment = await service.create_comment(
        poll_id=poll_id,
        user_id=current_user.user_id,
        content=data.content,
        parent_id=data.parent_id,
        option_id=data.option_id,
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Poll or parent comment not found")

    return PollCommentResponse(
        id=comment.id,
        pollId=comment.poll_id,
        userId=comment.user_id,
        content=comment.content,
        optionId=comment.option_id,
        likes=comment.likes,
        depth=comment.depth,
        createdAt=comment.created_at,
        isDeleted=comment.is_deleted,
    )


@router.get(
    "/{poll_id}/comments",
    response_model=list[PollCommentResponse],
    summary="댓글 목록 (트리)",
)
async def list_comments(
    poll_id: uuid.UUID,
    service: CommentServiceDep,
) -> list[PollCommentResponse]:
    """여론조사 댓글을 트리 구조로 조회합니다."""
    tree = await service.get_comments_tree(poll_id)

    def node_to_response(node) -> PollCommentResponse:
        return PollCommentResponse(
            id=node.id,
            pollId=node.poll_id,
            userId=node.user_id,
            userName=node.user_name,
            userImage=node.user_image,
            content=node.content,
            optionId=node.option_id,
            likes=node.likes,
            depth=node.depth,
            createdAt=node.created_at,
            isDeleted=node.is_deleted,
            replies=[node_to_response(r) for r in node.replies],
        )

    return [node_to_response(n) for n in tree]


# ========================================
# Research Endpoints (Admin Only)
# ========================================

@router.post(
    "/{poll_id}/research",
    response_model=ResearchTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="팩트 리서치 트리거 (관리자)",
)
async def trigger_research(
    poll_id: uuid.UUID,
    current_admin: CurrentAdmin,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchTriggerResponse:
    """여론조사에 대한 팩트 리서치를 비동기로 시작합니다. 관리자 전용."""
    research_service = request.app.state.research_service
    if research_service is None or not research_service.enabled:
        raise HTTPException(
            status_code=503,
            detail="Research service is not configured. Check API keys.",
        )

    # Poll 존재 확인
    service = PollService(session)
    poll = await service.get_poll(poll_id)
    if poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")

    # 이미 실행 중인지 확인
    status_info = research_service.get_status(str(poll_id))
    if status_info["status"] == "running":
        raise HTTPException(status_code=409, detail="Research is already running for this poll")

    # 백그라운드에서 새 세션으로 리서치 실행
    from app.core.database import AsyncSessionLocal

    async def _run_research():
        async with AsyncSessionLocal() as bg_session:
            await research_service.run_research(poll_id, bg_session)

    background_tasks.add_task(_run_research)

    return ResearchTriggerResponse(status="started", pollId=poll_id)


@router.get(
    "/{poll_id}/research/status",
    response_model=ResearchStatusResponse,
    summary="리서치 상태 조회 (관리자)",
)
async def get_research_status(
    poll_id: uuid.UUID,
    current_admin: CurrentAdmin,
    request: Request,
) -> ResearchStatusResponse:
    """여론조사 팩트 리서치의 진행 상태를 조회합니다. 관리자 전용."""
    research_service = request.app.state.research_service
    if research_service is None:
        raise HTTPException(status_code=503, detail="Research service is not available")

    status_info = research_service.get_status(str(poll_id))
    return ResearchStatusResponse(
        status=status_info["status"],
        pollId=poll_id,
        error=status_info.get("error"),
    )


# ========================================
# View Count
# ========================================

@router.post(
    "/{poll_id}/view",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="조회수 증가",
)
async def increment_view_count(
    poll_id: uuid.UUID,
    service: PollServiceDep,
) -> None:
    """여론조사 조회수를 증가시킵니다."""
    await service.increment_view_count(poll_id)
