"""
Cloudflare Free/Pro geo-blocking middleware.

Reads the CF-IPCountry header and blocks vote requests
from outside allowed countries.

Pure ASGI middleware — does not use BaseHTTPMiddleware to preserve
SQLAlchemy async greenlet context.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

_VOTE_PATTERN = re.compile(r"^/api/v1/polls/[0-9a-f-]{36}/vote$")


class CloudflareProMiddleware:
    """Block vote requests from outside allowed countries using Cloudflare geo headers."""

    def __init__(
        self,
        app: ASGIApp,
        allowed_countries: set[str] | None = None,
    ) -> None:
        self.app = app
        self.allowed_countries = allowed_countries or {"KR"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # To prevent the middleware from being called for non-HTTP requests (e.g. WebSocket, etc.)
        # To prevent KeyError or nonsensical behavior
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # To prevent the middleware from being called if the request is not a vote request
        # This is a performance optimization to prevent the middleware from being called for non-vote requests
        method = scope.get("method", "")
        path = scope.get("path", "")

        # To prevent the middleware from being called if the request is not a vote request
        # This is a performance optimization to prevent the middleware from being called for non-vote requests
        if not self._is_vote_request(method, path):
            await self.app(scope, receive, send)
            return

        # Vote request — enforce geo restriction.
        country = self._get_header(scope, b"cf-ipcountry")

        # To prevent the middleware from being called if the CF-IPCountry header is missing
        # This is a performance optimization to prevent the middleware from being called for non-vote requests
        if not country:
            logger.warning(
                "CF-IPCountry header missing on vote request: %s %s",
                method,
                path,
            )
            await self._send_403(
                send,
                detail="Unable to verify request origin.",
                code="GEO_MISSING",
            )
            return

        # pass through if the country is in the allowed countries
        if country.upper() in self.allowed_countries:
            await self.app(scope, receive, send)
            return

        # Blocked.
        logger.info(
            "Geo-blocked vote request from country=%s path=%s",
            country,
            path,
        )
        await self._send_403(
            send,
            detail="Access restricted to South Korea.",
            code="GEO_BLOCKED",
            extra={"country": country.upper()},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_header(scope: Scope, name: bytes) -> str | None:
        """Find a single header value by lowercase name from raw ASGI headers."""
        for key, value in scope.get("headers", []):
            if key.lower() == name:
                return value.decode("latin-1")
        return None

    @staticmethod
    def _is_vote_request(method: str, path: str) -> bool:
        return method == "POST" and _VOTE_PATTERN.match(path) is not None

    @staticmethod
    async def _send_403(
        send: Send,
        detail: str,
        code: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Send a 403 JSON response directly via the ASGI send callable."""
        body_dict: dict[str, Any] = {"detail": detail, "code": code}
        if extra:
            body_dict.update(extra)
        body = json.dumps(body_dict).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )
