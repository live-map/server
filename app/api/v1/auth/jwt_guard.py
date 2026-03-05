"""
JWT Guard - Authentication interceptor for FastAPI routes.

Validates JWT access tokens issued by the backend auth service.
Tokens are signed with HS256 using JWT_SECRET.

Supports:
1. Bearer token authentication (Authorization: Bearer <token>)
2. Cookie-based authentication (grapoll-access-token cookie)
"""

import logging
from dataclasses import dataclass
from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes for Type-Safe Token Payload
# ============================================================


@dataclass
class JWTPayload:
    """
    Decoded JWT token payload.

    Attributes:
        user_id: User identifier from token.sub
        email: User email
        name: User display name
        role: User role (USER or ADMIN)
        exp: Token expiration timestamp
        iat: Token issued at timestamp
    """

    user_id: str
    email: str | None
    name: str | None
    role: str
    exp: int | None = None
    iat: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "JWTPayload":
<<<<<<< HEAD
        """
        Create JWTPayload from decoded JWT dictionary.

        Args:
            data: Decoded JWT payload dictionary

        Returns:
            JWTPayload: Structured token payload
        """
        user_id = data.get("id", data.get("sub", ""))
        if not user_id:
            raise InvalidTokenError(
                status_code=401,
                message="Invalid JWT: missing user identifier (id or sub)",
            )
        return cls(
            user_id=user_id,
=======
        """Create JWTPayload from decoded JWT dictionary."""
        return cls(
            user_id=data.get("sub", ""),
>>>>>>> a8d1096 (refactor: authentication)
            email=data.get("email"),
            name=data.get("name"),
            role=data.get("role", "USER"),
            exp=data.get("exp"),
            iat=data.get("iat"),
        )


# ============================================================
# Token Extraction
# ============================================================

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="JWT access token",
    auto_error=False,
)

# Cookie names for access token
ACCESS_COOKIE_NAME = "grapoll-access-token"
ACCESS_COOKIE_NAME_SECURE = "__Secure-grapoll-access-token"


async def get_token_from_header(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    """Extract JWT token from Authorization: Bearer header."""
    if credentials is None:
        return None
    return credentials.credentials


async def get_token_from_cookie(request: Request) -> str | None:
    """Extract JWT token from cookie."""
    for cookie_name in [ACCESS_COOKIE_NAME_SECURE, ACCESS_COOKIE_NAME]:
        token = request.cookies.get(cookie_name)
        if token:
            return token
    return None


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Raises:
        pyjwt.ExpiredSignatureError: If token has expired
        pyjwt.InvalidTokenError: If token is invalid
    """
    return pyjwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ============================================================
# JWT Validation Dependencies (Guards)
# ============================================================


async def get_current_user_optional(
    request: Request,
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload | None:
    """
    Get current user from JWT token (optional).

    Returns None if no token is found or token is invalid.
    Use for routes that work for both authenticated and anonymous users.
    """
    token_from_cookie = await get_token_from_cookie(request)
    token = token_from_header or token_from_cookie

    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return JWTPayload.from_dict(payload)
    except pyjwt.ExpiredSignatureError:
        logger.debug("JWT token expired (optional auth)")
        return None
    except pyjwt.InvalidTokenError as e:
        logger.debug(f"Invalid JWT token (optional auth): {e}")
        return None


async def get_current_user(
    request: Request,
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload:
    """
    Get current user from JWT token (required).

    Raises HTTPException 401 if no valid token is found.
    Use for protected routes that REQUIRE authentication.
    """
    token_from_cookie = await get_token_from_cookie(request)
    token = token_from_header or token_from_cookie

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a valid JWT token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return JWTPayload.from_dict(payload)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_admin(
    current_user: Annotated[JWTPayload, Depends(get_current_user)],
) -> JWTPayload:
    """
    Get current user and verify admin role.
    Raises 403 if user is not an admin.
    """
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user


# ============================================================
# Type Aliases for Dependency Injection
# ============================================================

CurrentUserOptional = Annotated[JWTPayload | None, Depends(get_current_user_optional)]
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]
CurrentAdmin = Annotated[JWTPayload, Depends(get_current_admin)]
