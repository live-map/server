"""
FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
API docs: http://localhost:8000/docs
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.lifespan import lifespan

logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.APP_NAME,
    description="Grapoll - 여론조사 플랫폼 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
_cors_origins = [settings.FRONTEND_URL]
if settings.DEBUG:
    _cors_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with consistent error response."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    content: dict = {"detail": "Internal server error"}
    if settings.DEBUG:
        content["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=content)


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
