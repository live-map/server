"""
Application configuration using Pydantic Settings.

Environment variables are loaded from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Grapoll API"
    DEBUG: bool = False

    # Database (Backend - polls, posts, etc.)
    DATABASE_URL: str = "postgresql+asyncpg://livemap:livemap123@localhost:5432/livemap"

    # Database (Frontend/Auth - shared with NextAuth for user data)
    AUTH_DATABASE_URL: str | None = None

    # JWT/Auth Configuration
    # This MUST match the AUTH_SECRET in the frontend's .env file
    AUTH_SECRET: str

    # Frontend URL for CORS and cookie settings
    FRONTEND_URL: str = "http://localhost:3000"

    # AWS S3 Configuration
    AWS_S3_BUCKET_NAME: str | None = None
    AWS_S3_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # CloudFront Configuration (optional, for CDN delivery)
    AWS_CLOUDFRONT_DOMAIN: str | None = None

    # Media Upload Settings
    MEDIA_UPLOAD_MAX_SIZE_MB: int = 100
    MEDIA_PRESIGNED_URL_EXPIRES: int = 3600

    @property
    def s3_enabled(self) -> bool:
        """Check if S3 is properly configured."""
        return bool(
            self.AWS_S3_BUCKET_NAME
            and self.AWS_ACCESS_KEY_ID
            and self.AWS_SECRET_ACCESS_KEY
        )


settings = Settings()
