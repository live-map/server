"""
Application lifespan events.

Handles startup and shutdown operations like model loading,
scheduler management, and database cleanup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML models on startup, cleanup on shutdown."""
    logger.info("Loading Stage 1 NLP models...")

    # Lazy import to avoid loading models at import time
    from app.services.verification.stage1.pipeline import load_all_models

    load_all_models()
    logger.info("Stage 1 models loaded successfully")

    # Start scheduler if enabled
    if settings.ENABLE_SCHEDULER:
        from app.services.scheduler import start_scheduler

        channels = None
        if settings.TELEGRAM_CHANNELS:
            channels = [c.strip() for c in settings.TELEGRAM_CHANNELS.split(",") if c.strip()]

        start_scheduler(channels=channels)
        logger.info("Background scheduler started")

    yield

    # Stop scheduler on shutdown
    if settings.ENABLE_SCHEDULER:
        from app.services.scheduler import stop_scheduler

        stop_scheduler()

    # Dispose DB engine
    from app.core.database import engine

    await engine.dispose()
    logger.info("Shutting down...")
