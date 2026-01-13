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

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://livemap:livemap123@localhost:5432/livemap"

    # Publishable Criteria
    PUBLISHABLE_MIN_CREDIBILITY: int = 60
    PUBLISHABLE_REQUIRE_LOCATION: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
