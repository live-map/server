"""
JWT Test Controller - API route handlers for user authentication endpoints.

Handles HTTP requests for user authentication and information retrieval.
Uses FastAPI's dependency injection for authentication and database sessions.

Architecture Flow:
1. Request hits this controller (routes)
2. JWT Guard validates the token (interpreter/jwt_guard.py)
3. Controller calls Service layer (service.py)
4. Service calls Repository layer (repository.py)
5. Repository queries Database
6. Response flows back up the chain

References:
- FastAPI Routing: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Dependency Injection: https://fastapi.tiangolo.com/tutorial/dependencies/
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.interpreter import CurrentAdmin, CurrentUser, CurrentUserOptional
from app.api.v1.jwt_test.schemas import (
    AuthStatusResponse,
    HealthResponse,
    JWTPayloadResponse,
    UserInfoResponse,
    UserListResponse,
    UserResponse,
    UserValidationResponse,
)
from app.api.v1.jwt_test.service import UserService
from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Dependency: UserService
# ============================================================


async def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    """
    Dependency that provides UserService instance.

    Creates a new UserService with the injected database session.
    This follows the dependency injection pattern for clean architecture.

    Args:
        db: Database session from get_db dependency

    Returns:
        UserService: Service instance for user operations
    """
    return UserService(db)


# Type alias for cleaner route signatures
UserServiceDep = Annotated[UserService, Depends(get_user_service)]


# ============================================================
# Public Routes (No Authentication Required)
# ============================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Auth Health Check",
    description="Check if authentication is properly configured",
)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthResponse:
    """
    Health check endpoint for authentication system.

    Verifies:
    - AUTH_SECRET is configured
    - Database connection is working

    Returns:
        HealthResponse: Health status of auth system
    """
    # Check AUTH_SECRET
    auth_configured = bool(settings.AUTH_SECRET)

    # Check database connection
    database_connected = False
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        database_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    return HealthResponse(
        status="ok" if (auth_configured and database_connected) else "degraded",
        auth_configured=auth_configured,
        database_connected=database_connected,
    )


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Authentication Status",
    description="Check if the current request is authenticated",
)
async def auth_status(
    current_user: CurrentUserOptional,
) -> AuthStatusResponse:
    """
    Check authentication status without requiring authentication.

    This endpoint works for both authenticated and unauthenticated requests.
    Returns the authentication status and basic user info if authenticated.

    Args:
        current_user: Current user from JWT (None if not authenticated)

    Returns:
        AuthStatusResponse: Authentication status
    """
    if current_user is None:
        return AuthStatusResponse(
            authenticated=False,
            user_id=None,
            role=None,
        )

    return AuthStatusResponse(
        authenticated=True,
        user_id=current_user.user_id,
        role=current_user.role,
    )


# ============================================================
# Protected Routes (Authentication Required)
# ============================================================


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Get Current User",
    description="Get information about the currently authenticated user",
)
async def get_current_user_info(
    current_user: CurrentUser,
    service: UserServiceDep,
    fetch_from_db: Annotated[
        bool,
        Query(
            description="Whether to fetch additional data from database (slower but more complete)"
        ),
    ] = True,
) -> UserInfoResponse:
    """
    Get current user information.

    Flow:
    1. JWT Guard (CurrentUser) validates the token
    2. Extract user info from JWT payload
    3. Optionally fetch additional data from database
    4. Return combined user information

    This endpoint demonstrates the full flow:
    Controller -> Service -> Repository -> Database

    Args:
        current_user: Authenticated user from JWT (injected by CurrentUser)
        service: UserService instance (injected by UserServiceDep)
        fetch_from_db: Whether to query database for additional info

    Returns:
        UserInfoResponse: User information
    """
    logger.info(f"GET /me called by user: {current_user.user_id}")

    # Call service layer to get user info
    user_info = await service.get_user_info(current_user, fetch_from_db=fetch_from_db)

    return UserInfoResponse(
        user_id=user_info.user_id,
        email=user_info.email,
        name=user_info.name,
        role=user_info.role,
        email_verified=user_info.email_verified,
        image=user_info.image,
        created_at=user_info.created_at,
        updated_at=user_info.updated_at,
        from_database=user_info.from_database,
    )


@router.get(
    "/me/token",
    response_model=JWTPayloadResponse,
    summary="Get JWT Token Payload",
    description="Get the decoded JWT token payload for debugging",
)
async def get_token_payload(
    current_user: CurrentUser,
) -> JWTPayloadResponse:
    """
    Get the decoded JWT token payload.

    This endpoint is useful for debugging and verifying token contents.
    It returns the raw JWT payload data without database queries.

    Args:
        current_user: Authenticated user from JWT

    Returns:
        JWTPayloadResponse: Decoded JWT payload
    """
    logger.info(f"GET /me/token called by user: {current_user.user_id}")

    return JWTPayloadResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        exp=current_user.exp,
        iat=current_user.iat,
        jti=current_user.jti,
    )


@router.get(
    "/me/validate",
    response_model=UserValidationResponse,
    summary="Validate User in Database",
    description="Validate that the authenticated user exists in the database",
)
async def validate_user_in_database(
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserValidationResponse:
    """
    Validate that the authenticated user exists in the database.

    This checks if the user ID from the JWT exists in the database.
    Useful for detecting stale tokens after user deletion.

    Args:
        current_user: Authenticated user from JWT
        service: UserService instance

    Returns:
        UserValidationResponse: Validation result with exists flag
    """
    logger.info(f"GET /me/validate called by user: {current_user.user_id}")

    exists = await service.validate_user_exists(current_user.user_id)

    return UserValidationResponse(
        user_id=current_user.user_id,
        exists_in_database=exists,
        message="User found in database" if exists else "User not found in database",
    )


# ============================================================
# Admin Routes (Admin Role Required)
# ============================================================


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List All Users (Admin)",
    description="Get a paginated list of all users (admin only)",
)
async def list_users(
    current_admin: CurrentAdmin,
    service: UserServiceDep,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of users per page")] = 20,
    offset: Annotated[int, Query(ge=0, description="Number of users to skip")] = 0,
) -> UserListResponse:
    """
    List all users with pagination.

    This endpoint is restricted to admin users only.
    The CurrentAdmin dependency validates both authentication and admin role.

    Args:
        current_admin: Authenticated admin user (injected by CurrentAdmin)
        service: UserService instance
        limit: Maximum number of users to return
        offset: Number of users to skip

    Returns:
        UserListResponse: Paginated list of users
    """
    logger.info(f"GET /users called by admin: {current_admin.user_id}")

    users = await service.list_users(limit=limit, offset=offset)
    total = await service.get_user_count()

    return UserListResponse(
        users=[
            UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role,
                email_verified=user.email_verified is not None,
                image=user.image,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get User by ID (Admin)",
    description="Get a specific user by ID (admin only)",
)
async def get_user_by_id(
    user_id: str,
    current_admin: CurrentAdmin,
    service: UserServiceDep,
) -> UserResponse:
    """
    Get a specific user by their ID.

    This endpoint is restricted to admin users only.

    Args:
        user_id: The user's CUID
        current_admin: Authenticated admin user
        service: UserService instance

    Returns:
        UserResponse: User information

    Raises:
        HTTPException: 404 if user not found
    """
    logger.info(f"GET /users/{user_id} called by admin: {current_admin.user_id}")

    user = await service.get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        email_verified=user.email_verified is not None,
        image=user.image,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
