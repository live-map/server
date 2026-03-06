"""
JWT token creation and validation.

Issues access tokens (short-lived) and refresh tokens (long-lived)
using PyJWT with HS256 signing. Both token types are JWTs
distinguished by the "type" claim ("access" vs "refresh").
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_access_token(user_id: str, email: str | None, name: str | None, role: str) -> str:
    """
    Create a short-lived access token (JWT).

    Args:
        user_id: User's database ID
        email: User's email
        name: User's display name
        role: User's role (USER or ADMIN)

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, email: str | None, name: str | None, role: str) -> str:
    """
    Create a long-lived refresh token (JWT).

    The refresh token carries the same user claims as the access token
    but with type="refresh" and a longer expiration (days instead of minutes).

    Args:
        user_id: User's database ID
        email: User's email
        name: User's display name
        role: User's role (USER or ADMIN)

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access token.

    Args:
        token: JWT string

    Returns:
        Decoded payload dict

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def decode_refresh_token(token: str) -> dict:
    """
    Decode and validate a refresh token.

    Verifies the JWT signature and checks that type="refresh".

    Args:
        token: JWT string

    Returns:
        Decoded payload dict

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid or not a refresh token
    """
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")
    return payload
