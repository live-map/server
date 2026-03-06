"""
Token Refresh Middleware - Stateless auto-refresh of expired access tokens.

Uses pure ASGI middleware (NOT BaseHTTPMiddleware) to avoid breaking
SQLAlchemy async session greenlet context.

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
from http.cookies import SimpleCookie

import jwt as pyjwt
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
)

# Cookie names
ACCESS_COOKIE = "grapoll-access-token"
ACCESS_COOKIE_SECURE = "__Secure-grapoll-access-token"
REFRESH_COOKIE = "grapoll-refresh-token"
REFRESH_COOKIE_SECURE = "__Secure-grapoll-refresh-token"


class TokenRefreshMiddleware:
    """Pure ASGI middleware that auto-refreshes expired access tokens using refresh JWTs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]

        # Skip auth endpoints and public routes
        if self._should_skip(path):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        cookies = self._parse_cookies(headers)

        access_token = self._get_access_token(headers, cookies)
        refresh_token = self._get_refresh_token(headers, cookies)

        new_access_token = None

        if access_token:
            try:
                payload = pyjwt.decode(
                    access_token,
                    settings.JWT_SECRET,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                if payload.get("type") == "access":
                    # Valid access token → pass through
                    await self.app(scope, receive, send)
                    return
            except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
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
                scope["headers"] = self._replace_auth_header(
                    scope["headers"], new_access_token
                )
                logger.debug("Auto-refreshed access token for user %s", refresh_payload["sub"])
            except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError) as e:
                logger.debug("Refresh token invalid: %s", e)

        if not new_access_token:
            # Nothing to inject in response → pass through
            await self.app(scope, receive, send)
            return

        # Wrap send to inject X-New-Access-Token into response headers
        token_to_inject = new_access_token

        async def send_with_token(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-new-access-token", token_to_inject.encode())
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_token)

    def _should_skip(self, path: str) -> bool:
        if path == "/":
            return True
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    def _parse_cookies(self, headers: dict[bytes, bytes]) -> dict[str, str]:
        raw = headers.get(b"cookie", b"").decode()
        if not raw:
            return {}
        cookie = SimpleCookie(raw)
        return {k: v.value for k, v in cookie.items()}

    def _get_access_token(
        self, headers: dict[bytes, bytes], cookies: dict[str, str]
    ) -> str | None:
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        for name in (ACCESS_COOKIE_SECURE, ACCESS_COOKIE):
            if name in cookies:
                return cookies[name]
        return None

    def _get_refresh_token(
        self, headers: dict[bytes, bytes], cookies: dict[str, str]
    ) -> str | None:
        token = headers.get(b"x-refresh-token", b"").decode()
        if token:
            return token
        for name in (REFRESH_COOKIE_SECURE, REFRESH_COOKIE):
            if name in cookies:
                return cookies[name]
        return None

    def _replace_auth_header(
        self, headers: list[tuple[bytes, bytes]], new_token: str
    ) -> list[tuple[bytes, bytes]]:
        new_headers = [
            (k, v) for k, v in headers if k.lower() != b"authorization"
        ]
        new_headers.append(
            (b"authorization", f"Bearer {new_token}".encode())
        )
        return new_headers
