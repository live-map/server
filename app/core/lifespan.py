"""
Application lifespan events.

Handles startup and shutdown operations.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("Starting Livemap API...")

    yield

    # Dispose DB engine on shutdown
    from app.core.database import engine

    await engine.dispose()
    logger.info("Shutting down...")
