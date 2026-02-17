"""
Authentication service - orchestrates OAuth, user management, and token issuance.
"""

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.user import User
from app.services.auth.jwt import create_access_token, create_refresh_token
from app.services.auth.oauth import exchange_code_for_token, fetch_user_profile

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def get_or_create_user(
    db: AsyncSession,
    provider: str,
    profile: dict,
    oauth_tokens: dict,
) -> User:
    """
    Find existing user by OAuth account or create a new one.

    Args:
        db: Database session
        provider: OAuth provider name (google, kakao)
        profile: Normalized user profile from OAuth provider
        oauth_tokens: Raw token response from OAuth provider

    Returns:
        User model instance
    """
    provider_account_id = profile["provider_account_id"]

    # Check if this OAuth account is already linked to a user
    result = await db.execute(
        select(User)
        .join(Account, Account.user_id == User.id)
        .where(Account.provider == provider)
        .where(Account.provider_account_id == provider_account_id)
    )
    user = result.scalar_one_or_none()

    if user:
        logger.info(f"Returning user found by OAuth account: {user.id} ({provider})")
        # Update OAuth tokens on the account
        account_result = await db.execute(
            select(Account)
            .where(Account.provider == provider)
            .where(Account.provider_account_id == provider_account_id)
        )
        account = account_result.scalar_one()
        account.access_token = oauth_tokens.get("access_token")
        account.refresh_token = oauth_tokens.get("refresh_token")
        account.expires_at = oauth_tokens.get("expires_at")
        account.id_token = oauth_tokens.get("id_token")
        await db.commit()
        return user

    # Check if a user with this email already exists (link account)
    if profile.get("email"):
        result = await db.execute(
            select(User).where(User.email == profile["email"])
        )
        user = result.scalar_one_or_none()

    if user:
        logger.info(f"Linking new OAuth account to existing user: {user.id} ({provider})")
    else:
        # Create new user
        from cuid2 import cuid_wrapper

        generate_cuid = cuid_wrapper()
        user = User(
            id=generate_cuid(),
            name=profile.get("name"),
            email=profile.get("email"),
            image=profile.get("image"),
            role="USER",
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created new user: {user.id} ({provider})")

    # Link OAuth account
    from cuid2 import cuid_wrapper

    generate_cuid = cuid_wrapper()
    account = Account(
        id=generate_cuid(),
        user_id=user.id,
        type="oauth",
        provider=provider,
        provider_account_id=provider_account_id,
        access_token=oauth_tokens.get("access_token"),
        refresh_token=oauth_tokens.get("refresh_token"),
        expires_at=oauth_tokens.get("expires_at"),
        token_type=oauth_tokens.get("token_type"),
        scope=oauth_tokens.get("scope"),
        id_token=oauth_tokens.get("id_token"),
    )
    db.add(account)
    await db.commit()

    return user


async def authenticate_oauth(
    db: AsyncSession,
    provider: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """
    Full OAuth authentication flow:
    1. Exchange authorization code for tokens
    2. Fetch user profile from provider
    3. Find or create user in database
    4. Issue our own JWT tokens

    Args:
        db: Database session
        provider: OAuth provider name
        code: Authorization code from provider
        redirect_uri: Redirect URI used in the authorization request

    Returns:
        Dict with access_token, refresh_token, token_type, expires_in, and user info
    """
    # Step 1: Exchange code for OAuth tokens
    oauth_tokens = await exchange_code_for_token(provider, code, redirect_uri)

    # Step 2: Fetch user profile from resource server
    profile = await fetch_user_profile(provider, oauth_tokens["access_token"])

    # Step 3: Find or create user
    user = await get_or_create_user(db, provider, profile, oauth_tokens)

    # Step 4: Issue our own tokens
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
    )
    refresh_token, refresh_expires_at = create_refresh_token(user.id)

    # Store refresh token hash in sessions table
    from app.models.session import Session as SessionModel
    from cuid2 import cuid_wrapper

    generate_cuid = cuid_wrapper()
    session_record = SessionModel(
        id=generate_cuid(),
        session_token=_hash_token(refresh_token),
        user_id=user.id,
        expires=refresh_expires_at,
    )
    db.add(session_record)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "image": user.image,
            "role": user.role,
        },
    }


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    """
    Validate refresh token and issue a new access token.

    Args:
        db: Database session
        refresh_token: The refresh token string

    Returns:
        Dict with new access_token

    Raises:
        ValueError: If refresh token is invalid or expired
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.session import Session as SessionModel

    token_hash = _hash_token(refresh_token)

    result = await db.execute(
        select(SessionModel).where(SessionModel.session_token == token_hash)
    )
    session_record = result.scalar_one_or_none()

    if not session_record:
        raise ValueError("Invalid refresh token")

    if session_record.expires < datetime.now(timezone.utc):
        # Clean up expired token
        await db.delete(session_record)
        await db.commit()
        raise ValueError("Refresh token has expired")

    # Fetch user
    result = await db.execute(
        select(User).where(User.id == session_record.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    # Issue new access token
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
    }


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> None:
    """
    Revoke (delete) a refresh token.

    Args:
        db: Database session
        refresh_token: The refresh token string to revoke
    """
    from app.models.session import Session as SessionModel

    token_hash = _hash_token(refresh_token)

    result = await db.execute(
        select(SessionModel).where(SessionModel.session_token == token_hash)
    )
    session_record = result.scalar_one_or_none()

    if session_record:
        await db.delete(session_record)
        await db.commit()
