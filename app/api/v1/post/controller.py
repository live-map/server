"""
Post Controller - API route handlers for post endpoints.

게시글 CRUD, 미디어, 좋아요 API를 제공합니다.
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

from app.api.v1.interpreter import CurrentUser, CurrentAdmin, CurrentUserOptional
from app.api.v1.post.dto.schemas import (
    LikeResponse,
    PostCreate,
    PostLikerResponse,
    PostLikersListResponse,
    PostListResponse,
    PostMediaCreate,
    PostMediaResponse,
    PostResponse,
    PostUpdate,
)
from app.api.v1.post.service import PostService, PostNotFoundError, PostPermissionError
from app.api.v1.post.media.service import PostMediaService
from app.api.v1.post.like.service import PostLikeService, PostNotFoundForLikeError
from app.api.v1.post.sort import SortType
from app.core.database import get_db
from app.models.post_media import MediaType

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


async def get_media_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PostMediaService:
    """PostMediaService 의존성 주입."""
    return PostMediaService(session)


async def get_like_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PostLikeService:
    """PostLikeService 의존성 주입."""
    return PostLikeService(session)


postServiceDep = Annotated[PostService, Depends(get_post_service)]
mediaServiceDep = Annotated[PostMediaService, Depends(get_media_service)]
likeServiceDep = Annotated[PostLikeService, Depends(get_like_service)]

# ========================================
# Post Endpoints
# ========================================

@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
    description="새 게시글을 작성합니다. 미디어 첨부 가능. 인증 필요.",
)
async def create_post(
    data: PostCreate,
    current_user: CurrentUser,
    postService: Annotated[PostService, Depends(get_post_service)],
    mediaService: mediaServiceDep,
) -> PostResponse:
    """
    새 게시글을 작성합니다.

    - **title**: 게시글 제목 (1-200자)
    - **content**: 게시글 내용
    - **media**: 미디어 첨부 (선택, S3 업로드 후 URL 전달, 최대 10개)

    Note: 게시글과 미디어는 단일 트랜잭션으로 처리됩니다.
    미디어 저장 실패 시 게시글 생성도 롤백됩니다.
    """
    # 게시글 생성 (아직 commit하지 않음 - 트랜잭션 시작)
    post = await postService.create_post_without_commit(
        user_id=current_user.user_id,
        title=data.title,
        content=data.content,
    )

    # 미디어 첨부 처리 (같은 트랜잭션 내에서)
    media_responses = []
    if data.media:
        media_data_list = [
            {
                "media_type": m.media_type,  # Already correct enum from import
                "url": m.url,
                "thumbnail_url": m.thumbnail_url,
                "original_filename": m.original_filename,
                "file_size": m.file_size,
                "duration": m.duration,
                "width": m.width,
                "height": m.height,
                "order": m.order,
            }
            for m in data.media
        ]
        created_media = await mediaService.add_multiple_media_without_commit(
            post_id=post.id,
            media_data_list=media_data_list,
        )
        media_responses = [
            PostMediaResponse(
                id=m.id,
                post_id=m.post_id,
                media_type=m.media_type,
                url=m.url,
                thumbnail_url=m.thumbnail_url,
                original_filename=m.original_filename,
                file_size=m.file_size,
                duration=m.duration,
                width=m.width,
                height=m.height,
                order=m.order,
                created_at=m.created_at,
            )
            for m in created_media
        ]

    # 모든 작업이 성공하면 한 번에 commit
    await postService.session.commit()

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        content=post.content,
        like_count=0,
        is_liked=False,
        media=media_responses,
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
    likeService: likeServiceDep,
    current_user: CurrentUserOptional = None,
    limit: Annotated[int, Query(ge=1, le=100, description="최대 조회 수")] = 20,
    offset: Annotated[int, Query(ge=0, description="건너뛸 수")] = 0,
    user_id: Annotated[str | None, Query(description="특정 사용자의 글만 조회")] = None,
    sort: Annotated[SortType, Query(description="정렬 기준")] = SortType.NEWEST,
) -> PostListResponse:
    """
    게시글 목록을 조회합니다.

    - **limit**: 최대 조회 수 (기본 20, 최대 100)
    - **offset**: 건너뛸 수 (기본 0)
    - **sort**: 정렬 기준 (popular, newest, most_viewed, most_liked, daily_hot, weekly_hot, monthly_hot)

    인증된 사용자의 경우 각 게시글의 좋아요 여부(is_liked)가 포함됩니다.
    """
    posts = await postService.list_posts(limit=limit, offset=offset, user_id=user_id, sort=sort)
    total = await postService.post_repo.count(user_id=user_id, sort=sort)

    # 인증된 사용자인 경우 좋아요 상태 일괄 조회
    like_status = {}
    if current_user:
        post_ids = [post.id for post in posts]
        like_status = await likeService.get_like_status_for_posts(post_ids, current_user.user_id)

    items = [
        PostResponse(
            id=post.id,
            user_id=post.user_id,
            user_name=post.user.name if post.user else None,
            title=post.title,
            content=post.content,
            like_count=post.like_count,
            view_count=post.view_count,
            is_liked=like_status.get(post.id, False),
            media=[
                PostMediaResponse(
                    id=m.id,
                    post_id=m.post_id,
                    media_type=m.media_type,
                    url=m.url,
                    thumbnail_url=m.thumbnail_url,
                    original_filename=m.original_filename,
                    file_size=m.file_size,
                    duration=m.duration,
                    width=m.width,
                    height=m.height,
                    order=m.order,
                    created_at=m.created_at,
                )
                for m in (post.media or [])
            ],
            created_at=post.created_at,
            updated_at=post.updated_at,
            comment_count=post.comment_count,
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
    likeService: likeServiceDep,
    current_user: CurrentUserOptional = None,
) -> PostResponse:
    """게시글 상세 정보를 조회합니다."""
    post = await service.get_post_with_comments(post_id)

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # 인증된 사용자인 경우 좋아요 여부 확인
    is_liked = False
    if current_user:
        is_liked = await likeService.is_liked_by_user(post_id, current_user.user_id)

    # Increment view count
    post.view_count += 1
    await service.session.flush()
    await service.session.commit()
    await service.session.refresh(post)

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        user_name=post.user.name if post.user else None,
        title=post.title,
        content=post.content,
        like_count=post.like_count,
        view_count=post.view_count,
        is_liked=is_liked,
        media=[
            PostMediaResponse(
                id=m.id,
                post_id=m.post_id,
                media_type=m.media_type,
                url=m.url,
                thumbnail_url=m.thumbnail_url,
                original_filename=m.original_filename,
                file_size=m.file_size,
                duration=m.duration,
                width=m.width,
                height=m.height,
                order=m.order,
                created_at=m.created_at,
            )
            for m in (post.media or [])
        ],
        created_at=post.created_at,
        updated_at=post.updated_at,
        comment_count=post.comment_count,
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
    try:
        post = await service.update_post(
            post_id=post_id,
            user_id=current_user.user_id,
            title=data.title,
            content=data.content,
        )
    except PostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    except PostPermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the owner of this post",
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
    try:
        await service.delete_post(
            post_id=post_id,
            user_id=current_user.user_id,
        )
    except PostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    except PostPermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the owner of this post",
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


# ========================================
# Like Endpoints
# ========================================

@router.post(
    "/{post_id}/like",
    response_model=LikeResponse,
    summary="게시글 좋아요",
    description="게시글에 좋아요를 추가합니다. 인증 필요.",
)
async def like_post(
    post_id: uuid.UUID,
    current_user: CurrentUser,
    likeService: likeServiceDep,
) -> LikeResponse:
    """
    게시글에 좋아요를 추가합니다.

    이미 좋아요한 경우 실패를 반환합니다.

    Note: 게시글 존재 확인은 서비스 레이어에서 수행됩니다.
    이는 컨트롤러 확인과 서비스 실행 사이의 race condition을 방지합니다.
    """
    try:
        result = await likeService.like_post(post_id, current_user.user_id)
    except PostNotFoundForLikeError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or has been deleted",
        )

    return LikeResponse(
        success=result.success,
        is_liked=result.is_liked,
        like_count=result.like_count,
        message=result.message,
    )


@router.delete(
    "/{post_id}/like",
    response_model=LikeResponse,
    summary="게시글 좋아요 취소",
    description="게시글 좋아요를 취소합니다. 인증 필요.",
)
async def unlike_post(
    post_id: uuid.UUID,
    current_user: CurrentUser,
    likeService: likeServiceDep,
) -> LikeResponse:
    """
    게시글 좋아요를 취소합니다.

    좋아요하지 않은 경우 실패를 반환합니다.
    """
    result = await likeService.unlike_post(post_id, current_user.user_id)
    return LikeResponse(
        success=result.success,
        is_liked=result.is_liked,
        like_count=result.like_count,
        message=result.message,
    )


@router.get(
    "/{post_id}/likes",
    response_model=PostLikersListResponse,
    summary="게시글 좋아요 목록",
    description="게시글을 좋아요한 사용자 목록을 조회합니다.",
)
async def get_post_likers(
    post_id: uuid.UUID,
    likeService: likeServiceDep,
    postService: postServiceDep,
    limit: Annotated[int, Query(ge=1, le=100, description="최대 조회 수")] = 20,
    offset: Annotated[int, Query(ge=0, description="건너뛸 수")] = 0,
) -> PostLikersListResponse:
    """
    게시글을 좋아요한 사용자 목록을 조회합니다.
    """
    # 게시글 존재 확인
    post = await postService.get_post(post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    likes = await likeService.get_post_likers(post_id, limit, offset)
    total = await likeService.get_like_count(post_id)

    items = [
        PostLikerResponse(
            user_id=like.user_id,
            user_name=like.user.name if like.user else None,
            user_image=like.user.image if like.user else None,
            liked_at=like.created_at,
        )
        for like in likes
    ]

    return PostLikersListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# ========================================
# Media Endpoints
# ========================================

@router.post(
    "/{post_id}/media",
    response_model=PostMediaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글에 미디어 추가",
    description="기존 게시글에 미디어를 추가합니다. 작성자만 가능.",
)
async def add_media_to_post(
    post_id: uuid.UUID,
    data: PostMediaCreate,
    current_user: CurrentUser,
    postService: postServiceDep,
    mediaService: mediaServiceDep,
) -> PostMediaResponse:
    """
    기존 게시글에 미디어를 추가합니다.

    S3 업로드 후 URL과 메타데이터를 전달합니다.
    작성자만 추가 가능합니다.
    """
    # 게시글 존재 및 권한 확인
    post = await postService.get_post(post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    if post.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the owner of this post",
        )

    media = await mediaService.add_media_to_post(
        post_id=post_id,
        media_type=MediaType(data.media_type.value),
        url=data.url,
        thumbnail_url=data.thumbnail_url,
        original_filename=data.original_filename,
        file_size=data.file_size,
        duration=data.duration,
        width=data.width,
        height=data.height,
        order=data.order,
    )

    return PostMediaResponse(
        id=media.id,
        post_id=media.post_id,
        media_type=media.media_type,
        url=media.url,
        thumbnail_url=media.thumbnail_url,
        original_filename=media.original_filename,
        file_size=media.file_size,
        duration=media.duration,
        width=media.width,
        height=media.height,
        order=media.order,
        created_at=media.created_at,
    )


@router.delete(
    "/{post_id}/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 미디어 삭제",
    description="게시글의 특정 미디어를 삭제합니다. 작성자만 가능.",
)
async def delete_media_from_post(
    post_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: CurrentUser,
    postService: postServiceDep,
    mediaService: mediaServiceDep,
) -> None:
    """
    게시글의 특정 미디어를 삭제합니다.

    Note: S3의 실제 파일은 별도로 삭제해야 합니다.
    작성자만 삭제 가능합니다.
    """
    # 게시글 존재 및 권한 확인
    post = await postService.get_post(post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    if post.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the owner of this post",
        )

    # 미디어가 해당 게시글에 속하는지 확인
    media = await mediaService.get_media_by_id(media_id)
    if media is None or media.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found",
        )

    result = await mediaService.delete_media(media_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found",
        )