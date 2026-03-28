"""
Application configuration using Pydantic Settings.

Environment variables are loaded from .env file.
"""

from pydantic import AnyHttpUrl, field_validator
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
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Database (Frontend/Auth - shared with NextAuth for user data)
    AUTH_DATABASE_URL: str | None = None

    # JWT Configuration
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 30 → 15 (auto-refresh middleware handles UX)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 30 → 7

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_be_set(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. "
                "Generate with: openssl rand -hex 64"
            )
        return v

    # Frontend URL for CORS and cookie settings
    FRONTEND_URL: AnyHttpUrl = "http://localhost:3000"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""

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
