"""
Media API Controller - Endpoints for media upload operations.

Provides:
- GET /media/config - Get upload configuration (public)
- POST /media/presigned-url - Generate presigned URL for S3 upload (auth required)
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.v1.interpreter import CurrentUser
from app.api.v1.media.schemas import (
    MediaConfigResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
)
from app.core.config import settings
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])


# ========================================
# Constants
# ========================================

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/webm"]


# ========================================
# Public Endpoints
# ========================================


@router.get(
    "/config",
    response_model=MediaConfigResponse,
    summary="Get media upload configuration",
    description="Returns upload limits and allowed file types. No authentication required.",
)
async def get_media_config() -> MediaConfigResponse:
    """
    미디어 업로드 설정 조회.

    프론트엔드에서 업로드 전 제한사항을 확인할 때 사용합니다.
    """
    return MediaConfigResponse(
        enabled=s3_service.is_available,
        max_file_size_mb=settings.MEDIA_UPLOAD_MAX_SIZE_MB,
        allowed_image_types=ALLOWED_IMAGE_TYPES,
        allowed_video_types=ALLOWED_VIDEO_TYPES,
        cloudfront_enabled=bool(settings.AWS_CLOUDFRONT_DOMAIN),
    )


# ========================================
# Protected Endpoints
# ========================================


@router.post(
    "/presigned-url",
    response_model=PresignedUrlResponse,
    summary="Generate presigned URL for S3 upload",
    description="Generates a presigned URL that allows direct upload to S3 from the browser.",
    responses={
        400: {"description": "Invalid content type"},
        503: {"description": "S3 service not available"},
    },
)
async def generate_presigned_url(
    request: PresignedUrlRequest,
    current_user: CurrentUser,
) -> PresignedUrlResponse:
    """
    S3 업로드용 Presigned URL 생성.

    1. 프론트엔드에서 이 엔드포인트를 호출하여 URL을 받습니다.
    2. 받은 upload_url로 파일을 직접 S3에 PUT 업로드합니다.
    3. 업로드 완료 후 access_url을 사용하여 미디어를 게시글에 등록합니다.

    Args:
        request: 파일명, content_type, 폴더 정보

    Returns:
        upload_url: S3 업로드용 presigned URL
        key: S3 객체 키
        access_url: 업로드 후 접근할 URL (CloudFront 또는 S3)
        expires_in: URL 만료 시간 (초)

    Raises:
        400: 허용되지 않은 content_type
        503: S3 서비스 미설정
    """
    # Validate file size (before S3 check — reject invalid requests early)
    max_bytes = settings.MEDIA_UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if request.file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MEDIA_UPLOAD_MAX_SIZE_MB}MB",
        )

    # Validate content type
    all_allowed_types = set(ALLOWED_IMAGE_TYPES + ALLOWED_VIDEO_TYPES)
    if request.content_type not in all_allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{request.content_type}' is not allowed. "
            f"Allowed types: {', '.join(sorted(all_allowed_types))}",
        )

    # Check if S3 is available (after input validation)
    if not s3_service.is_available:
        logger.error(f"S3 upload attempted but service not available. User: {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media upload service is not available. Please contact administrator.",
        )

    try:
        result = s3_service.generate_presigned_upload_url(
            filename=request.filename,
            content_type=request.content_type,
            folder=request.folder,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to generate upload URL",
            )

        logger.info(
            f"Generated presigned URL for user {current_user.user_id}: "
            f"{request.filename} -> {result['key']}"
        )

        return PresignedUrlResponse(
            upload_url=result["upload_url"],
            key=result["key"],
            access_url=result["access_url"],
            expires_in=settings.MEDIA_PRESIGNED_URL_EXPIRES,
        )

    except ValueError as e:
        # Content type validation error from S3 service
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        # S3 client error
        logger.error(f"S3 error generating presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to generate upload URL. Please try again.",
        )
