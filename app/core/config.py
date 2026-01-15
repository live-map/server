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
    AUTH_SECRET: str = ""

    # Frontend URL for CORS and cookie settings
    FRONTEND_URL: str = "http://localhost:3000"

    # Publishable Criteria
    PUBLISHABLE_MIN_CREDIBILITY: int = 60
    PUBLISHABLE_REQUIRE_LOCATION: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
