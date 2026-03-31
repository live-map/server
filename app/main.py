"""
FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
API docs: http://localhost:8000/docs
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.auth.refresh_middleware import TokenRefreshMiddleware
from app.middleware.cloudflare_pro import CloudflareProMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.lifespan import lifespan
from app.core.limiter import limiter

logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.APP_NAME,
    description="Grapoll - 여론조사 플랫폼 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Attach rate limiter to app state
app.state.limiter = limiter

# CORS middleware for Next.js frontend
_cors_origins = [str(settings.FRONTEND_URL).rstrip("/")]
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
    allow_headers=["Content-Type", "Authorization", "Cookie", "X-Refresh-Token"],
    expose_headers=["X-New-Access-Token"],
)


# Token refresh middleware (auto-refreshes expired access tokens)
app.add_middleware(TokenRefreshMiddleware)

# Cloudflare geo-blocking middleware (blocks non-KR vote requests)
app.add_middleware(CloudflareProMiddleware)

# Rate limiting middleware (must be after CORS)
app.add_middleware(SlowAPIMiddleware)

# X-Request-ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a unique X-Request-ID to every request/response."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with consistent error response."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    content: dict = {"detail": "Internal server error"}
    if settings.DEBUG:
        content["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """Return 422 for request validation errors instead of 500."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint with DB connectivity verification."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "service": settings.APP_NAME}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": settings.APP_NAME, "error": "database connection failed"},
        )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
