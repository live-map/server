"""
Auth Controller - OAuth login, token refresh, logout, and user info endpoints.
"""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dto.schemas import (
    AuthResponse,
    AuthUrlResponse,
    LogoutRequest,
    OAuthCallbackRequest,
    TokenRefreshRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.api.v1.auth.jwt_guard import CurrentUser
from app.api.v1.auth.lib.oauth import get_authorization_url, get_provider_config
from app.api.v1.auth.repository import AuthRepository
from app.api.v1.auth.service import AuthService
from app.core.database import get_db
from app.core.limiter import limiter


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# Endpoints
# ============================================================

# get_oauth_authorize_url - Generate OAuth authorization URL for the given provider
# This endpoint is used to add Client ID and Redirect URI to the OAuth authorization URL

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
        #  validate the provider is supported
        get_provider_config(provider)
        # remove the debug logging for production
        logger.debug(f"redirect_uri: {redirect_uri}")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )
    # generate a random state for CSRF protection
    # this state is echoed back by the provider in the callback
    # and is used to verify the request was not forged
    # the state is also used to prevent replay attacks by the provider
    state = secrets.token_urlsafe(32)
    # generate the OAuth authorization URL that contains the Client ID and Redirect URI
    url = get_authorization_url(provider, redirect_uri, state)

    return AuthUrlResponse(url=url, state=state)

# To exchange the authorization code for an access token, the frontend sends the authorization code to the backend
@router.post(
    "/oauth/{provider}/callback",
    response_model=AuthResponse, # FastAPI uses this to validate the response body and generate the response JSON on Swagger UI
)
@limiter.limit("10/minute")
async def oauth_callback(
    request: Request,
    provider: str,
    body: OAuthCallbackRequest,
    service: AuthService = Depends(),
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
        result = await service.authenticate_oauth(provider, body.code, body.redirect_uri)
    except Exception as e:
        logger.error(f"OAuth authentication failed for {provider}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth authentication failed. Please try again.",
        )

    return AuthResponse(**result)


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
@limiter.limit("20/minute")
async def refresh_token(request: Request, body: TokenRefreshRequest):
    """
    Refresh an access token using a valid refresh token.

    The frontend sends its refresh token when the access token expires.
    Returns a new access token without requiring the user to log in again.

    This is a stateless operation — the refresh token is a JWT and is
    validated by decoding it (no DB lookup needed).
    """
    try:
        result = AuthService.refresh_access_token(body.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return TokenResponse(**result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest):
    """
    Logout endpoint.

    With stateless JWT refresh tokens, server-side revocation is not performed.
    The client clears its cookies. The access token expires naturally (30 min).
    """
    # No-op on the server side. Client clears cookies.
    pass


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


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the currently authenticated user's profile.

    Only name and image can be updated.
    """
    repo = AuthRepository(db)
    user = await repo.find_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.name is not None:
        user.name = body.name
    if body.image is not None:
        user.image = body.image

    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        image=user.image,
        role=user.role,
    )
