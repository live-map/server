"""
Auth Controller - OAuth login, token refresh, logout, and user info endpoints.
"""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.interpreter import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.services.auth.oauth import get_authorization_url, get_provider_config
from app.services.auth.service import authenticate_oauth, refresh_access_token, revoke_refresh_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# Request/Response Schemas / DTO
# ============================================================


class OAuthCallbackRequest(BaseModel):
    """Request body for OAuth callback."""

    code: str
    state: str | None = None
    redirect_uri: str


class TokenRefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body for logout."""

    refresh_token: str | None = None


class AuthResponse(BaseModel):
    """Response for successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: dict


class TokenResponse(BaseModel):
    """Response for token refresh."""

    access_token: str
    token_type: str = "Bearer"


class AuthUrlResponse(BaseModel):
    """Response containing OAuth authorization URL."""

    url: str
    state: str


class UserResponse(BaseModel):
    """Response for current user info."""

    id: str
    email: str | None
    name: str | None
    image: str | None
    role: str


# ============================================================
# Endpoints
# ============================================================


@router.get(
    "/oauth/{provider}/authorize",
    response_model=AuthUrlResponse,
)
async def get_oauth_authorize_url(
    provider: str,
    redirect_uri: str = Query(..., description="Frontend callback URL"),
):
    """
    Generate OAuth authorization URL for the given provider.

    The frontend redirects the user's browser to this URL.
    After the user grants consent, the provider redirects back
    to redirect_uri with an authorization code.
    """
    try:
        get_provider_config(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )

    state = secrets.token_urlsafe(32)
    url = get_authorization_url(provider, redirect_uri, state)

    return AuthUrlResponse(url=url, state=state)


@router.post(
    "/oauth/{provider}/callback",
    response_model=AuthResponse,
)
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle OAuth callback - exchange code for tokens and authenticate user.

    The frontend sends the authorization code received from the provider.
    The backend:
    1. Exchanges the code for an OAuth access token
    2. Fetches the user's profile from the provider
    3. Creates or finds the user in the database
    4. Issues our own JWT access + refresh tokens
    """
    try:
        get_provider_config(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )

    try:
        result = await authenticate_oauth(db, provider, body.code, body.redirect_uri)
    except Exception as e:
        logger.error(f"OAuth authentication failed for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth authentication failed. Please try again.",
        )

    return AuthResponse(**result)


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh_token(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh an access token using a valid refresh token.

    The frontend sends its refresh token when the access token expires.
    Returns a new access token without requiring the user to log in again.
    """
    try:
        result = await refresh_access_token(db, body.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return TokenResponse(**result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Logout - revoke the refresh token.

    The frontend sends the refresh token to invalidate it.
    The access token will expire naturally (short-lived).
    """
    if body.refresh_token:
        await revoke_refresh_token(db, body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """
    Get the currently authenticated user's info.

    Requires a valid access token in the Authorization header.
    """
    return UserResponse(
        id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        image=None,
        role=current_user.role,
    )
