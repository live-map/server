"""
Auth Repository - Data access layer for User and Account models.
"""

import logging

from cuid2 import cuid_wrapper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.account import Account
from app.models.user import Role, User

logger = logging.getLogger(__name__)

generate_cuid = cuid_wrapper()


class AuthRepository:
    """Repository for auth-related database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_user_and_account_by_oauth(
        self,
        provider: str,
        provider_account_id: str,
    ) -> tuple[User, Account] | None:
        """OAuth 계정(provider + provider_account_id)으로 사용자와 계정을 한 번에 조회."""
        result = await self.session.execute(
            select(User, Account)
            .join(Account, Account.user_id == User.id)
            .where(Account.provider == provider)
            .where(Account.provider_account_id == provider_account_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row.tuple()

    async def find_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def update_account_tokens(
        self,
        account: Account, # Account object to update
        oauth_tokens: dict, # OAuth tokens to update
    ) -> None:
        """OAuth 계정의 토큰 정보 업데이트."""
        account.access_token = oauth_tokens.get("access_token")
        account.refresh_token = oauth_tokens.get("refresh_token")
        account.expires_at = oauth_tokens.get("expires_at")
        account.id_token = oauth_tokens.get("id_token")
        await self.session.commit()

    async def create_user(self, profile: dict) -> User:
        """새 사용자 생성."""
        user = User(
            id=generate_cuid(),
            name=profile.get("name"),
            email=profile.get("email"),
            image=profile.get("image"),
            role=Role.USER,
        )
        self.session.add(user)
        await self.session.flush()
        logger.info("Created new user: %s", user.id)
        return user

    async def create_account(
        self,
        user_id: str,
        provider: str,
        provider_account_id: str,
        oauth_tokens: dict,
    ) -> Account:
        """OAuth 계정 생성 및 사용자 연결."""
        account = Account(
            id=generate_cuid(),
            user_id=user_id,
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
        self.session.add(account)
        await self.session.commit()
        logger.info("Created OAuth account for user %s (%s)", user_id, provider)
        return account
