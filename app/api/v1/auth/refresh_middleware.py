"""
Token Refresh Middleware - Stateless auto-refresh of expired access tokens.

Intercepts every request and transparently refreshes expired access tokens
using the JWT refresh token. Both tokens are JWTs signed with the same secret,
so no DB lookups are needed.

Flow:
1. Skip auth-related and public endpoints
2. Extract access token from Authorization header or cookie
3. Extract refresh token from X-Refresh-Token header or cookie
4. If access token is valid → pass through
5. If access token is expired/missing AND refresh token is valid:
   - Create new access token from refresh token claims
   - Inject into request Authorization header
   - Add X-New-Access-Token response header
6. If both fail → pass through (downstream guard raises 401)
"""

import logging

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.auth.jwt import create_access_token, decode_refresh_token
from app.core.config import settings

logger = logging.getLogger(__name__)

# Paths that should skip token refresh
SKIP_PREFIXES = (
    "/api/v1/auth/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
)

# Cookie names
ACCESS_COOKIE = "grapoll-access-token"
ACCESS_COOKIE_SECURE = "__Secure-grapoll-access-token"
REFRESH_COOKIE = "grapoll-refresh-token"
REFRESH_COOKIE_SECURE = "__Secure-grapoll-refresh-token"


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware that auto-refreshes expired access tokens using refresh JWTs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip auth endpoints and public routes
        path = request.url.path
        if self._should_skip(path):
            return await call_next(request)

        # Extract tokens
        access_token = self._get_access_token(request)
        refresh_token = self._get_refresh_token(request)

        new_access_token = None

        if access_token:
            # Check if access token is still valid
            try:
                payload = pyjwt.decode(
                    access_token,
                    settings.JWT_SECRET,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                if payload.get("type") == "access":
                    # Valid access token → pass through
                    return await call_next(request)
            except pyjwt.ExpiredSignatureError:
                # Access token expired → try refresh below
                pass
            except pyjwt.InvalidTokenError:
                # Invalid access token → try refresh below
                pass

        # No valid access token — attempt refresh
        if refresh_token:
            try:
                refresh_payload = decode_refresh_token(refresh_token)
                new_access_token = create_access_token(
                    user_id=refresh_payload["sub"],
                    email=refresh_payload.get("email"),
                    name=refresh_payload.get("name"),
                    role=refresh_payload.get("role", "USER"),
                )
                # Inject new token into request headers
                request.scope["headers"] = self._replace_auth_header(
                    request.scope["headers"], new_access_token
                )
                logger.debug("Auto-refreshed access token for user %s", refresh_payload["sub"])
            except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError) as e:
                logger.debug("Refresh token invalid: %s", e)

        # Call the actual endpoint
        response = await call_next(request)

        # If we refreshed, add the new token to response header
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token

        return response

    def _should_skip(self, path: str) -> bool:
        """Check if the path should skip token refresh."""
        # Exact match for root
        if path == "/":
            return True
        # Prefix match for other skip paths (but not root)
        for prefix in SKIP_PREFIXES:
            if prefix != "/" and path.startswith(prefix):
                return True
        return False

    def _get_access_token(self, request: Request) -> str | None:
        """Extract access token from Authorization header or cookie."""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        # Fallback to cookie
        for name in (ACCESS_COOKIE_SECURE, ACCESS_COOKIE):
            token = request.cookies.get(name)
            if token:
                return token
        return None

    def _get_refresh_token(self, request: Request) -> str | None:
        """Extract refresh token from X-Refresh-Token header or cookie."""
        token = request.headers.get("x-refresh-token")
        if token:
            return token
        # Fallback to cookie
        for name in (REFRESH_COOKIE_SECURE, REFRESH_COOKIE):
            token = request.cookies.get(name)
            if token:
                return token
        return None

    def _replace_auth_header(
        self, headers: list[tuple[bytes, bytes]], new_token: str
    ) -> list[tuple[bytes, bytes]]:
        """Replace or add the Authorization header in the ASGI scope."""
        new_headers = [
            (k, v) for k, v in headers if k.lower() != b"authorization"
        ]
        new_headers.append(
            (b"authorization", f"Bearer {new_token}".encode())
        )
        return new_headers
