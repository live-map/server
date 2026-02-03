"""
Application configuration using Pydantic Settings.

Environment variables are loaded from .env file.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Livemap API"
    DEBUG: bool = True

    # Database (Backend - feeds, channels, etc.)
    DATABASE_URL: str = "postgresql+asyncpg://livemap:livemap123@localhost:5432/livemap"

    # Database (Frontend/Auth - shared with NextAuth for user data)
    # This connects to the same Supabase PostgreSQL where NextAuth stores users
    AUTH_DATABASE_URL: str | None = None  # e.g., postgresql+asyncpg://user:pass@host:5432/db

    # JWT/Auth Configuration
    # This MUST match the AUTH_SECRET in the frontend's .env file
    # Generate with: openssl rand -base64 32
    AUTH_SECRET: str = "E8VqfS2mKh5Cso1u3wwIShpGGNQBMhwHiD2a6x/MpuA="

    # Frontend URL for CORS and cookie settings
    FRONTEND_URL: str = "http://localhost:3000"

    # Publishable Criteria
    PUBLISHABLE_MIN_CREDIBILITY: int = 60
    PUBLISHABLE_REQUIRE_LOCATION: bool = False

    # AWS S3 Configuration
    # Required for media uploads. Get credentials from AWS IAM.
    AWS_S3_BUCKET_NAME: str | None = None
    AWS_S3_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # CloudFront Configuration (optional, for CDN delivery)
    # If not set, S3 direct URLs will be used
    AWS_CLOUDFRONT_DOMAIN: str | None = None  # e.g., "d1234abcd.cloudfront.net"

    # Media Upload Settings
    MEDIA_UPLOAD_MAX_SIZE_MB: int = 100  # Max file size in MB
    MEDIA_PRESIGNED_URL_EXPIRES: int = 3600  # Presigned URL expiry in seconds (1 hour)

    @property
    def s3_enabled(self) -> bool:
        """Check if S3 is properly configured."""
        return bool(
            self.AWS_S3_BUCKET_NAME
            and self.AWS_ACCESS_KEY_ID
            and self.AWS_SECRET_ACCESS_KEY
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
