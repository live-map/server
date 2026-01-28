"""
Post Controller - API route handlers for post endpoints.

게시글 CRUD API만 제공합니다.
댓글 관련 API는 별도의 CommentController에서 처리합니다.

Architecture Flow (기존 jwt_test 모듈과 동일):
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

from app.api.v1.interpreter import CurrentUser, CurrentAdmin
from app.api.v1.post.dto.schemas import (
    PostCreate,
    PostListResponse,
    PostResponse,
    PostUpdate,
)
from app.api.v1.post.service import PostService
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])



# ========================================
# Dependencies
# ========================================

async def get_post_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PostService:
    """PostService 의존성 주입."""
    return PostService(session)

postServiceDep = Annotated[PostService, Depends(get_post_service)]

# ========================================
# Post Endpoints
# ========================================

@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
    description="새 게시글을 작성합니다. 인증 필요.",
)
async def create_post(
    data: PostCreate,
    current_user: CurrentUser,
    postService: Annotated[PostService, Depends(get_post_service)],
) -> PostResponse:
    """
    새 게시글을 작성합니다.

    - **title**: 게시글 제목 (1-200자)
    - **content**: 게시글 내용
    """
    post = await postService.create_post(
        user_id=current_user.user_id,
        title=data.title,
        content=data.content,
    )

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        comment_count=0,
    )


@router.get(
    "",
    response_model=PostListResponse,
    summary="게시글 목록 조회",
    description="게시글 목록을 페이지네이션으로 조회합니다.",
)
async def list_posts(
    postService: Annotated[PostService, Depends(get_post_service)],
    limit: Annotated[int, Query(ge=1, le=100, description="최대 조회 수")] = 20,
    offset: Annotated[int, Query(ge=0, description="건너뛸 수")] = 0,
) -> PostListResponse:
    """
    게시글 목록을 조회합니다.

    - **limit**: 최대 조회 수 (기본 20, 최대 100)
    - **offset**: 건너뛸 수 (기본 0)
    """
    posts = await postService.list_posts(limit=limit, offset=offset)
    total = await postService.post_repo.count()

    items = [
        PostResponse(
            id=post.id,
            user_id=post.user_id,
            user_name=post.user.name if post.user else None,
            title=post.title,
            content=post.content,
            created_at=post.created_at,
            updated_at=post.updated_at,
            comment_count=len(post.comments) if post.comments else 0,
        )
        for post in posts
    ]

    return PostListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 상세 조회",
    description="특정 게시글의 상세 정보를 조회합니다.",
)
async def get_post(
    post_id: uuid.UUID,
    service: postServiceDep,
) -> PostResponse:
    """게시글 상세 정보를 조회합니다."""
    post = await service.get_post_with_comments(post_id)

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        user_name=post.user.name if post.user else None,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        comment_count=len(post.comments) if post.comments else 0,
    )


@router.patch(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 수정",
    description="게시글을 수정합니다. 작성자만 가능.",
)
async def update_post(
    post_id: uuid.UUID,
    data: PostUpdate,
    current_user: CurrentUser,
    service: postServiceDep,
) -> PostResponse:
    """
    게시글을 수정합니다.

    작성자만 수정 가능합니다.
    """
    post = await service.update_post(
        post_id=post_id,
        user_id=current_user.user_id,
        title=data.title,
        content=data.content,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or no permission",
        )

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제 (소프트)",
    description="게시글을 소프트 삭제합니다. 작성자만 가능.",
)
async def delete_post(
    post_id: uuid.UUID,
    current_user: CurrentUser,
    service: postServiceDep,
) -> None:
    """
    게시글을 삭제합니다 (소프트 삭제).

    작성자만 삭제 가능합니다.
    """
    result = await service.delete_post(
        post_id=post_id,
        user_id=current_user.user_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or no permission",
        )

# This is only for admin to hard delete a post
@router.delete(
    "/{post_id}/hard",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 완전 삭제 (Admin Only)",
    description="게시글을 DB에서 완전 삭제합니다. 관리자만 가능.",
)
async def hard_delete_post(
    post_id: uuid.UUID,
    current_admin: CurrentAdmin,
    service: postServiceDep,
) -> None:
    """
    게시글을 완전 삭제합니다 (하드 삭제).

    CASCADE로 모든 댓글도 함께 삭제됩니다.
    관리자만 사용 가능합니다.
    """
    try:
        await service.post_repo.hard_delete(post_id)
        await service.session.commit()
        logger.info(f"Admin {current_admin.user_id} hard deleted post {post_id}")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )