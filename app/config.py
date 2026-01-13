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

    # API Keys (Stage 3)
    MISTRAL_API_KEY: str = ""  # Mistral AI for Stage 3

    # Stage 2 RAG (SearXNG)
    SEARXNG_URL: str = "http://localhost:8888"  # Self-hosted SearXNG
    ENABLE_RAG_STAGE2: bool = True  # Use RAG-based Stage 2

    # Scheduler
    ENABLE_SCHEDULER: bool = False  # Enable background collection
    TELEGRAM_CHANNELS: str = ""  # Comma-separated channel usernames

    # === Pipeline V2 Settings (Social Media) ===
    USE_PIPELINE_V2: bool = True  # Enable new 4-stage pipeline

    # Stage 0: Preprocessing
    STAGE0_MIN_TEXT_LENGTH: int = 20  # Minimum text length after normalization
    STAGE0_ENABLE_COORDINATE_EXTRACTION: bool = True
    STAGE0_ENABLE_TERMINOLOGY: bool = True

    # Stage 1: Source Credibility (V2)
    STAGE1_LOCATION_REQUIRED: bool = False  # Location is now OPTIONAL
    STAGE1_ENABLE_FAKE_NEWS_MODEL: bool = False  # Disabled for short posts
    STAGE1_ENABLE_SUBJECTIVITY: bool = False  # Disabled for short posts
    STAGE1_CHANNEL_WEIGHT: float = 0.4  # Weight for channel credibility (v2)
    STAGE1_LOCATION_WEIGHT: float = 0.2  # Weight for location presence (v2)
    STAGE1_COORDINATE_BONUS: float = 0.1  # Bonus for extracted coordinates (v2)

    # Duplicate Detection
    DUPLICATE_THRESHOLD_SHORT: float = 0.95  # < 100 chars
    DUPLICATE_THRESHOLD_MEDIUM: float = 0.90  # 100-280 chars
    DUPLICATE_THRESHOLD_LONG: float = 0.85  # > 280 chars

    # Stage 2: Multi-Source Search
    STAGE2_ENABLE_TELEGRAM_SEARCH: bool = True  # Search Telegram channels
    STAGE2_ENABLE_OSINT_SEARCH: bool = True  # Search OSINT trackers
    STAGE2_ENABLE_NEWS_SEARCH: bool = True  # Search news (SearXNG)
    STAGE2_REALTIME_PRIORITY_HOURS: int = 4  # Prioritize realtime sources for recent events
    STAGE2_MAX_SOURCES: int = 10  # Max sources to fetch per search type

    # Channel Credibility
    CHANNEL_DEFAULT_TIER: int = 5  # Default tier for unknown channels
    CHANNEL_MIN_POSTS_FOR_ACCURACY: int = 10  # Min posts before calculating accuracy
    CHANNEL_SUBSCRIBER_TIER1: int = 100000  # Tier 1: 100k+ subscribers
    CHANNEL_SUBSCRIBER_TIER2: int = 10000  # Tier 2: 10k+ subscribers
    CHANNEL_SUBSCRIBER_TIER3: int = 1000  # Tier 3: 1k+ subscribers
    CHANNEL_AGE_TIER1_DAYS: int = 730  # Tier 1: 2+ years
    CHANNEL_AGE_TIER2_DAYS: int = 365  # Tier 2: 1+ year

    # Publishable Criteria
    PUBLISHABLE_MIN_CREDIBILITY: int = 60  # Minimum credibility score
    PUBLISHABLE_REQUIRE_LOCATION: bool = False  # Location is now OPTIONAL

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
