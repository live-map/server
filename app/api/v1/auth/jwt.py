"""
JWT token creation and validation.

Issues access tokens (short-lived) and refresh tokens (long-lived)
using PyJWT with HS256 signing.
"""

import logging
import secrets
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


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    """
    Create a long-lived refresh token.

    Returns a tuple of (token_string, expiration_datetime).
    The token is an opaque random string, not a JWT.

    Args:
        user_id: User's database ID

    Returns:
        (token, expires_at) tuple
    """
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at


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
