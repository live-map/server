"""
Pydantic schemas for Media API endpoints.
"""

from typing import Literal

from pydantic import BaseModel, Field


class PresignedUrlRequest(BaseModel):
    """Request for generating a presigned upload URL."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename with extension (e.g., 'photo.jpg')",
        examples=["photo.jpg", "video.mp4"],
    )
    content_type: str = Field(
        ...,
        description="MIME type of the file",
        examples=["image/jpeg", "image/png", "video/mp4"],
    )
    folder: Literal["posts", "avatars", "comments"] = Field(
        default="posts",
        description="Destination folder for the upload",
    )


class PresignedUrlResponse(BaseModel):
    """Response containing presigned URL for upload."""

    upload_url: str = Field(
        ...,
        description="Presigned URL for PUT upload directly to S3",
    )
    key: str = Field(
        ...,
        description="S3 object key (path) for the file",
    )
    access_url: str = Field(
        ...,
        description="URL to access the file after upload (CloudFront or S3)",
    )
    expires_in: int = Field(
        ...,
        description="URL expiry time in seconds",
    )


class MediaConfigResponse(BaseModel):
    """Response containing media upload configuration."""

    enabled: bool = Field(
        ...,
        description="Whether media uploads are enabled (S3 configured)",
    )
    max_file_size_mb: int = Field(
        ...,
        description="Maximum file size allowed in MB",
    )
    allowed_image_types: list[str] = Field(
        ...,
        description="Allowed image MIME types",
    )
    allowed_video_types: list[str] = Field(
        ...,
        description="Allowed video MIME types",
    )
    cloudfront_enabled: bool = Field(
        ...,
        description="Whether CloudFront CDN is configured",
    )
