"""
JWT Test Service - Business logic layer for user operations.

Orchestrates operations between the controller and repository layers.
Contains business logic and validation rules for user-related operations.

References:
- Service Layer Pattern: https://martinfowler.com/eaaCatalog/serviceLayer.html
- FastAPI Dependency Injection: https://fastapi.tiangolo.com/tutorial/dependencies/
"""

import logging
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.interpreter import JWTPayload
from app.api.v1.jwt_test.repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    """
    User information DTO (Data Transfer Object).

    Combines JWT payload data with database user data.
    This is returned to the controller/route layer.
    """

    # From JWT token
    user_id: str
    email: str | None
    name: str | None
    role: str

    # From database (optional, if fetched)
    email_verified: bool = False
    image: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    # Metadata
    from_database: bool = False

    @classmethod
    def from_jwt(cls, jwt_payload: JWTPayload) -> "UserInfo":
        """
        Create UserInfo from JWT payload only.

        Args:
            jwt_payload: Decoded JWT token payload

        Returns:
            UserInfo: User information from token
        """
        return cls(
            user_id=jwt_payload.user_id,
            email=jwt_payload.email,
            name=jwt_payload.name,
            role=jwt_payload.role,
            from_database=False,
        )

    @classmethod
    def from_jwt_and_db(cls, jwt_payload: JWTPayload, user: User) -> "UserInfo":
        """
        Create UserInfo from JWT payload enriched with database data.

        Args:
            jwt_payload: Decoded JWT token payload
            user: User entity from database

        Returns:
            UserInfo: Complete user information
        """
        return cls(
            user_id=jwt_payload.user_id,
            email=user.email or jwt_payload.email,
            name=user.name or jwt_payload.name,
            role=user.role or jwt_payload.role,
            email_verified=user.email_verified is not None,
            image=user.image,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None,
            from_database=True,
        )


class UserService:
    """
    Service class for user-related business logic.

    Provides methods to:
    - Get user information from JWT and/or database
    - Validate user existence
    - List users (admin only)

    Usage:
        async with AsyncSessionLocal() as session:
            service = UserService(session)
            user_info = await service.get_user_info(jwt_payload)
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the service with a database session.

        The session is used to create the repository for database operations.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = UserRepository(session)

    async def get_user_info(self, jwt_payload: JWTPayload, fetch_from_db: bool = True) -> UserInfo:
        """
        Get user information from JWT and optionally from database.

        This method demonstrates the intentional (though inefficient) pattern
        of fetching user data from the database even when JWT contains the info.
        In production, you might skip the DB fetch for performance.

        Flow:
        1. Extract user info from JWT payload
        2. If fetch_from_db is True, query the database for additional data
        3. Merge JWT and DB data into UserInfo

        Args:
            jwt_payload: Decoded JWT token payload
            fetch_from_db: Whether to fetch additional data from database

        Returns:
            UserInfo: Combined user information
        """
        logger.info(f"Getting user info for user_id: {jwt_payload.user_id}")

        if not fetch_from_db:
            # Return only JWT data (more efficient)
            logger.debug("Returning user info from JWT only")
            return UserInfo.from_jwt(jwt_payload)

        # Fetch user from database (intentionally inefficient for testing)
        logger.debug("Fetching user from database")
        user = await self.repository.get_by_id(jwt_payload.user_id)

        if user is None:
            # User exists in JWT but not in database
            # This could happen if user was deleted after JWT was issued
            logger.warning(f"User {jwt_payload.user_id} not found in database")
            return UserInfo.from_jwt(jwt_payload)

        # Combine JWT and database data
        logger.debug(f"Found user in database: {user.email}")
        return UserInfo.from_jwt_and_db(jwt_payload, user)

    async def get_user_by_id(self, user_id: str) -> User | None:
        """
        Get user entity by ID.

        Args:
            user_id: The user's CUID

        Returns:
            User | None: User entity if found
        """
        return await self.repository.get_by_id(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        """
        Get user entity by email.

        Args:
            email: The user's email address

        Returns:
            User | None: User entity if found
        """
        return await self.repository.get_by_email(email)

    async def list_users(self, limit: int = 100, offset: int = 0) -> Sequence[User]:
        """
        List all users with pagination.

        This should only be called by admin users.
        Authorization should be checked at the controller level.

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip

        Returns:
            Sequence[User]: List of user entities
        """
        logger.info(f"Listing users: limit={limit}, offset={offset}")
        return await self.repository.get_all(limit=limit, offset=offset)

    async def get_user_count(self) -> int:
        """
        Get total number of users.

        Returns:
            int: Total user count
        """
        return await self.repository.count()

    async def validate_user_exists(self, user_id: str) -> bool:
        """
        Validate that a user exists in the database.

        Args:
            user_id: The user's CUID

        Returns:
            bool: True if user exists
        """
        return await self.repository.exists(user_id)
