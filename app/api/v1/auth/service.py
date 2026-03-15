"""
Authentication service - orchestrates OAuth, user management, and token issuance.

Refresh tokens are now stateless JWTs (no DB storage needed).
"""

import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.api.v1.auth.lib.oauth import exchange_code_for_token, fetch_user_profile
from app.api.v1.auth.repository import AuthRepository
from app.core.database import get_db

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication business logic."""

    def __init__(self, db: AsyncSession = Depends(get_db)) -> None:
        self.repo = AuthRepository(db)

    async def authenticate_oauth(
        self,
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
            provider: OAuth provider name
            code: Authorization code from provider
            redirect_uri: Redirect URI used in the authorization request

        Returns:
            Dict with access_token, refresh_token, token_type, and user info
        """
        # Step 1: Exchange code for OAuth tokens (access token and refresh token)
        oauth_tokens = await exchange_code_for_token(provider, code, redirect_uri)

        # Step 2: Fetch user profile from provider's resource server
        profile = await fetch_user_profile(provider, oauth_tokens["access_token"])

        # Step 3: Find or create user
        provider_account_id = profile["provider_account_id"]

        result = await self.repo.find_user_and_account_by_oauth(provider, provider_account_id)

        if result:
            (user, account) = result
            await self.repo.update_account_tokens(account, oauth_tokens)
        else:
            # Check if a user with this email already exists (link account)
            if profile.get("email"):
                user = await self.repo.find_user_by_email(profile["email"])

                if user:
                    logger.info(f"Linking new OAuth account to existing user: {user.id} ({provider})")
                else:
                    user = await self.repo.create_user(profile)
            else:
                # Create a new user if no email is provided
                user = await self.repo.create_user(profile)
            # Create a new account for the user // adding another account to the user
            await self.repo.create_account(user.id, provider, provider_account_id, oauth_tokens)

        # Step 4: Issue our own tokens (both are stateless JWTs)
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
        )

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

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """
        Validate a JWT refresh token and issue a new access token.

        Stateless: decodes the refresh JWT and creates a new access token
        from its claims. No DB lookup needed.

        Args:
            refresh_token: The refresh token JWT string

        Returns:
            Dict with new access_token

        Raises:
            ValueError: If refresh token is invalid or expired
        """
        import jwt

        try:
            payload = decode_refresh_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise ValueError("Refresh token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid refresh token: {e}")

        access_token = create_access_token(
            user_id=payload["sub"],
            email=payload.get("email"),
            name=payload.get("name"),
            role=payload.get("role", "USER"),
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
        }
