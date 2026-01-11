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

    # Telegram (existing)
    TELEGRAM_API_ID: str = ""
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://livemap:livemap123@localhost:5432/livemap"

    # API Keys (Stage 2-3)
    CLAIMBUSTER_API_KEY: str = ""  # https://idir.uta.edu/claimbuster/
    GOOGLE_API_KEY: str = ""  # Google Fact Check Tools API
    MISTRAL_API_KEY: str = ""  # Mistral AI for Stage 3

    # Stage 2 RAG (SearXNG)
    SEARXNG_URL: str = "http://localhost:8888"  # Self-hosted SearXNG
    ENABLE_RAG_STAGE2: bool = True  # Use RAG-based Stage 2

    # Scheduler
    ENABLE_SCHEDULER: bool = False  # Enable background collection
    TELEGRAM_CHANNELS: str = ""  # Comma-separated channel usernames

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
