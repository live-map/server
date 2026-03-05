"""
Auth DTO schemas - Request/Response models for auth endpoints.
"""

from pydantic import BaseModel


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
