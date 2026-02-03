"""
S3 Service - Handles AWS S3 operations for media uploads.

This service provides:
- Presigned URL generation for direct browser uploads
- CloudFront URL generation for CDN delivery
- File key management with organized folder structure

Usage:
    from app.services.s3_service import s3_service

    # Get presigned URL for upload
    result = s3_service.generate_presigned_upload_url(
        filename="photo.jpg",
        content_type="image/jpeg",
        folder="posts",
    )
    # Returns: { upload_url, key, access_url }
"""

import logging
import uuid
from datetime import datetime
from typing import Literal

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """
    AWS S3 서비스 - 미디어 업로드를 위한 presigned URL 생성.

    Features:
    - Presigned URL for direct browser-to-S3 uploads
    - CloudFront CDN URL generation (if configured)
    - Organized folder structure: {folder}/{year}/{month}/{uuid}_{filename}
    """

    def __init__(self) -> None:
        """Initialize S3 client with AWS credentials from settings."""
        self._client = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of S3 client."""
        if self._initialized:
            return

        if not settings.s3_enabled:
            logger.warning(
                "S3 is not configured. Set AWS_S3_BUCKET_NAME, "
                "AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY in .env"
            )
            self._initialized = True
            return

        try:
            self._client = boto3.client(
                "s3",
                region_name=settings.AWS_S3_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
            )
            self._initialized = True
            logger.info(
                f"S3 client initialized for bucket: {settings.AWS_S3_BUCKET_NAME}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self._initialized = True

    @property
    def is_available(self) -> bool:
        """Check if S3 service is available."""
        self._ensure_initialized()
        return self._client is not None

    def _generate_key(
        self,
        filename: str,
        folder: str = "uploads",
    ) -> str:
        """
        Generate unique S3 key with organized folder structure.

        Format: {folder}/{year}/{month}/{uuid}_{filename}
        Example: posts/2024/01/a1b2c3d4_photo.jpg
        """
        # Sanitize filename (remove path separators, limit length)
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        if len(safe_filename) > 100:
            ext = safe_filename.rsplit(".", 1)[-1] if "." in safe_filename else ""
            safe_filename = safe_filename[:90] + ("." + ext if ext else "")

        # Generate unique prefix
        date_prefix = datetime.utcnow().strftime("%Y/%m")
        unique_id = uuid.uuid4().hex[:8]

        return f"{folder}/{date_prefix}/{unique_id}_{safe_filename}"

    def _get_access_url(self, key: str) -> str:
        """
        Get the URL for accessing an uploaded file.

        Returns CloudFront URL if configured, otherwise S3 direct URL.
        """
        if settings.AWS_CLOUDFRONT_DOMAIN:
            # Remove protocol if included in domain
            domain = settings.AWS_CLOUDFRONT_DOMAIN.replace("https://", "").replace(
                "http://", ""
            )
            return f"https://{domain}/{key}"
        else:
            # Direct S3 URL
            return f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{key}"

    def generate_presigned_upload_url(
        self,
        filename: str,
        content_type: str,
        folder: Literal["posts", "avatars", "comments"] = "posts",
    ) -> dict | None:
        """
        Generate presigned URL for direct browser upload to S3.

        Args:
            filename: Original filename (e.g., "photo.jpg")
            content_type: MIME type (e.g., "image/jpeg", "video/mp4")
            folder: Upload destination folder

        Returns:
            dict with:
                - upload_url: Presigned URL for PUT upload
                - key: S3 object key
                - access_url: URL to access file after upload (CloudFront or S3)
            None if S3 is not configured

        Raises:
            ValueError: If content type is not allowed
            RuntimeError: If presigned URL generation fails
        """
        self._ensure_initialized()

        if not self.is_available:
            logger.error("S3 service is not available")
            return None

        # Validate content type
        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "video/mp4",
            "video/quicktime",
            "video/webm",
        }
        if content_type not in allowed_types:
            raise ValueError(
                f"Content type '{content_type}' is not allowed. "
                f"Allowed types: {', '.join(sorted(allowed_types))}"
            )

        # Generate unique key
        key = self._generate_key(filename, folder)

        try:
            # Generate presigned URL for PUT operation
            presigned_url = self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.AWS_S3_BUCKET_NAME,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=settings.MEDIA_PRESIGNED_URL_EXPIRES,
            )

            access_url = self._get_access_url(key)

            logger.info(f"Generated presigned URL for key: {key}")

            return {
                "upload_url": presigned_url,
                "key": key,
                "access_url": access_url,
            }

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise RuntimeError(f"Failed to generate upload URL: {e}")

    def generate_presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str | None:
        """
        Generate presigned URL for downloading a private S3 object.

        Note: If using CloudFront, you typically don't need this method
        as CloudFront handles access control.

        Args:
            key: S3 object key
            expires_in: URL expiry time in seconds

        Returns:
            Presigned download URL or None if S3 not available
        """
        self._ensure_initialized()

        if not self.is_available:
            return None

        try:
            presigned_url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_S3_BUCKET_NAME,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return presigned_url
        except ClientError as e:
            logger.error(f"Failed to generate presigned download URL: {e}")
            return None

    def delete_object(self, key: str) -> bool:
        """
        Delete an object from S3.

        Args:
            key: S3 object key

        Returns:
            True if deleted successfully, False otherwise
        """
        self._ensure_initialized()

        if not self.is_available:
            return False

        try:
            self._client.delete_object(
                Bucket=settings.AWS_S3_BUCKET_NAME,
                Key=key,
            )
            logger.info(f"Deleted S3 object: {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete S3 object {key}: {e}")
            return False

    def delete_objects(self, keys: list[str]) -> int:
        """
        Delete multiple objects from S3.

        Args:
            keys: List of S3 object keys

        Returns:
            Number of objects successfully deleted
        """
        self._ensure_initialized()

        if not self.is_available or not keys:
            return 0

        try:
            response = self._client.delete_objects(
                Bucket=settings.AWS_S3_BUCKET_NAME,
                Delete={"Objects": [{"Key": key} for key in keys]},
            )
            deleted_count = len(response.get("Deleted", []))
            logger.info(f"Deleted {deleted_count} S3 objects")
            return deleted_count
        except ClientError as e:
            logger.error(f"Failed to delete S3 objects: {e}")
            return 0


# Singleton instance
s3_service = S3Service()
