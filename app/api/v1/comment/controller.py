"""
Comment Controller - API route handlers for comment endpoints.

댓글 및 대댓글 CRUD API를 제공합니다.
게시글 관련 API는 별도의 PostController에서 처리합니다.

URL 설계:
- 완전히 독립된 /comments 경로 사용
- post_id는 query parameter로 필터링에 사용
- 이를 통해 Post 모듈과 Comment 모듈의 완전한 분리 달성

Architecture Flow:
1. Request hits this controller (routes)
2. JWT Guard validates the token (interpreter/jwt_guard.py)
3. Controller calls Service layer (service.py)
4. Service calls Repository layer (repository.py)
5. Repository queries Database
6. Response flows back up the chain
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.interpreter import CurrentUser
from app.api.v1.comment.dto.schemas import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentTreeListResponse,
    CommentTreeResponse,
    CommentUpdate,
)
from app.api.v1.comment.dto.commentTreeNode import CommentTreeNode
from app.api.v1.comment.service import CommentService
from app.core.database import get_db

logger = logging.getLogger(__name__)

# 완전히 독립된 /comments 경로 사용
router = APIRouter(prefix="/comments", tags=["comments"])


# ========================================
# Dependencies
# ========================================

async def get_comment_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CommentService:
    """CommentService 의존성 주입."""
    return CommentService(session)


# Type alias for cleaner route signatures
CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]


# ========================================
# Comment Endpoints (독립된 /comments 경로)
# ========================================

@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글/대댓글 작성",
    description="새 댓글 또는 대댓글을 작성합니다. 인증 필요.",
)
async def create_comment(
    data: CommentCreate,
    current_user: CurrentUser,
    commentService: Annotated[CommentService, Depends(get_comment_service)],
) -> CommentResponse:
    """
    댓글 또는 대댓글을 작성합니다.

    - **post_id**: 게시글 UUID (Request Body에 포함)
    - **content**: 댓글 내용 (1-1000자)
    - **parent_id**: 대댓글인 경우 부모 댓글 UUID (선택)
    """
    comment = await commentService.create_comment(
        post_id=data.post_id,
        user_id=current_user.user_id,
        content=data.content,
        parent_id=data.parent_id,
    )

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post or parent comment not found",
        )

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        depth=comment.depth,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get(
    "",
    response_model=CommentListResponse,
    summary="댓글 목록 조회 (플랫)",
    description="게시글의 댓글을 플랫 리스트로 조회합니다.",
)
async def list_comments_flat(
    service: CommentServiceDep,
    post_id: Annotated[uuid.UUID | None, Query(description="게시글 UUID")] = None,
    user_id: Annotated[str | None, Query(description="특정 사용자의 댓글만 조회")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="최대 조회 수")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 수")] = 0,
) -> CommentListResponse:
    """
    댓글을 플랫 리스트로 조회합니다.

    - **post_id**: Query parameter로 게시글 UUID 지정
    - **user_id**: Query parameter로 사용자 ID 지정

    post_id 또는 user_id 중 하나는 반드시 제공해야 합니다.
    """
    if not post_id and not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="post_id 또는 user_id 중 하나는 반드시 제공해야 합니다.",
        )

    # user_id만 제공된 경우: 사용자별 댓글 목록 + 수 반환
    if user_id and not post_id:
        comments = await service.get_user_comments(user_id, limit=limit, offset=offset)
        total = await service.get_user_comment_count(user_id)

        items = [
            CommentResponse(
                id=comment.id,
                post_id=comment.post_id,
                user_id=comment.user_id,
                user_name=comment.user.name if comment.user else None,
                parent_id=comment.parent_id,
                content=comment.content,
                depth=comment.depth,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                reply_count=0,
            )
            for comment in comments
        ]

        return CommentListResponse(items=items, total=total)

    # post_id가 제공된 경우: 기존 로직
    comments = await service.get_flat_comments(post_id, limit=limit, offset=offset)
    total = await service.get_comment_count(post_id)

    items = []
    for comment in comments:
        reply_count = await service.get_reply_count(comment.id)
        items.append(
            CommentResponse(
                id=comment.id,
                post_id=comment.post_id,
                user_id=comment.user_id,
                user_name=comment.user.name if comment.user else None,
                parent_id=comment.parent_id,
                content=comment.content,
                depth=comment.depth,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                reply_count=reply_count,
            )
        )

    return CommentListResponse(items=items, total=total)


@router.get(
    "/tree",
    response_model=CommentTreeListResponse,
    summary="댓글 목록 조회 (트리)",
    description="게시글의 댓글을 트리 구조로 조회합니다.",
)
async def list_comments_tree(
    service: CommentServiceDep,
    post_id: Annotated[uuid.UUID, Query(description="게시글 UUID")],
) -> CommentTreeListResponse:
    """
    게시글의 댓글을 트리 구조로 조회합니다.

    - **post_id**: Query parameter로 게시글 UUID 지정

    각 댓글의 replies 필드에 대댓글이 재귀적으로 포함됩니다.
    """
    tree = await service.get_comments_tree(post_id)
    total = await service.get_comment_count(post_id)

    def convert_node(node: CommentTreeNode) -> CommentTreeResponse:
        return CommentTreeResponse(
            id=node.id,
            user_id=node.user_id,
            user_name=node.user_name,
            content=node.content,
            depth=node.depth,
            created_at=node.created_at,
            is_deleted=node.is_deleted,
            replies=[convert_node(r) for r in node.replies],
        )

    items = [convert_node(node) for node in tree]

    return CommentTreeListResponse(items=items, total=total)


@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 상세 조회",
    description="특정 댓글의 상세 정보를 조회합니다.",
)
async def get_comment(
    comment_id: uuid.UUID,
    service: CommentServiceDep,
) -> CommentResponse:
    """댓글 상세 정보를 조회합니다 (comment_id로 직접 조회)."""
    comment = await service.comment_repo.get_by_id(comment_id)

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    reply_count = await service.get_reply_count(comment_id)

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        user_name=comment.user.name if comment.user else None,
        parent_id=comment.parent_id,
        content=comment.content,
        depth=comment.depth,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_deleted=comment.is_deleted,
        reply_count=reply_count,
    )


@router.patch(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 수정",
    description="댓글을 수정합니다. 작성자만 가능.",
)
async def update_comment(
    comment_id: uuid.UUID,
    data: CommentUpdate,
    current_user: CurrentUser,
    service: CommentServiceDep,
) -> CommentResponse:
    """
    댓글을 수정합니다.

    작성자만 수정 가능합니다.
    """
    comment = await service.update_comment(
        comment_id=comment_id,
        user_id=current_user.user_id,
        content=data.content,
    )

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or no permission",
        )

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        depth=comment.depth,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="댓글 삭제",
    description="댓글을 소프트 삭제합니다. 작성자만 가능.",
)
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: CurrentUser,
    service: CommentServiceDep,
) -> None:
    """
    댓글을 삭제합니다 (소프트 삭제).

    대댓글이 있는 경우 내용만 마스킹되고 구조는 유지됩니다.
    작성자만 삭제 가능합니다.
    """
    result = await service.delete_comment(
        comment_id=comment_id,
        user_id=current_user.user_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or no permission",
        )


@router.get(
    "/{comment_id}/replies",
    response_model=CommentListResponse,
    summary="대댓글 목록 조회",
    description="특정 댓글의 직접 대댓글만 조회합니다.",
)
async def list_replies(
    comment_id: uuid.UUID,
    service: CommentServiceDep,
    limit: Annotated[int, Query(ge=1, le=50, description="최대 조회 수")] = 20,
) -> CommentListResponse:
    """
    특정 댓글의 직접 대댓글만 조회합니다.

    무한 대댓글 구조에서 특정 댓글의 바로 아래 대댓글만 가져올 때 사용합니다.
    """
    replies = await service.comment_repo.get_replies(comment_id, limit=limit)
    total = await service.get_reply_count(comment_id)

    items = [
        CommentResponse(
            id=reply.id,
            post_id=reply.post_id,
            user_id=reply.user_id,
            user_name=reply.user.name if reply.user else None,
            parent_id=reply.parent_id,
            content=reply.content,
            depth=reply.depth,
            created_at=reply.created_at,
            updated_at=reply.updated_at,
            is_deleted=reply.is_deleted,
            reply_count=0,  # 하위 대댓글 수는 별도 조회 필요
        )
        for reply in replies
    ]

    return CommentListResponse(items=items, total=total)