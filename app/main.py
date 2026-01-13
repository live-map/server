"""
FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
API docs: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings

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
    from app.db.session import engine

    await engine.dispose()
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Real-time verified news feed API for global conflict monitoring",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with consistent error response."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
