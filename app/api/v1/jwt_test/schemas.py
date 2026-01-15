"""
JWT Test Schemas - Pydantic models for request/response validation.

These schemas define the structure of data for API requests and responses.
Uses Pydantic v2 syntax for improved performance and cleaner validation.

References:
- Pydantic v2 Documentation: https://docs.pydantic.dev/latest/
- FastAPI Response Models: https://fastapi.tiangolo.com/tutorial/response-model/
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleEnum(str, Enum):
    """User role enumeration matching Prisma/NextAuth roles."""

    USER = "USER"
    ADMIN = "ADMIN"


# ============================================================
# Response Schemas
# ============================================================


class UserBase(BaseModel):
    """
    Base user schema with common fields.

    Used as a base class for other user schemas.
    """

    id: str = Field(..., description="User's unique identifier (CUID)")
    email: EmailStr | None = Field(None, description="User's email address")
    name: str | None = Field(None, description="User's display name")
    role: RoleEnum = Field(default=RoleEnum.USER, description="User's role")


class UserResponse(UserBase):
    """
    User response schema for API responses.

    Contains user information returned from API endpoints.
    Excludes sensitive fields like hashed_password.
    """

    model_config = ConfigDict(from_attributes=True)

    email_verified: bool = Field(False, description="Whether email is verified")
    image: str | None = Field(None, description="User's profile image URL")
    created_at: datetime | None = Field(None, description="Account creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")


class UserInfoResponse(BaseModel):
    """
    User info response combining JWT and database data.

    This is the main response schema for the /me endpoint.
    """

    user_id: str = Field(..., description="User's unique identifier")
    email: str | None = Field(None, description="User's email address")
    name: str | None = Field(None, description="User's display name")
    role: str = Field(..., description="User's role (USER or ADMIN)")
    email_verified: bool = Field(False, description="Whether email is verified")
    image: str | None = Field(None, description="User's profile image URL")
    created_at: str | None = Field(None, description="Account creation timestamp (ISO format)")
    updated_at: str | None = Field(None, description="Last update timestamp (ISO format)")
    from_database: bool = Field(
        False, description="Whether data was fetched from database (True) or JWT only (False)"
    )


class UserListResponse(BaseModel):
    """
    Paginated user list response.

    Used for admin endpoints that list all users.
    """

    users: list[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    limit: int = Field(..., description="Number of users per page")
    offset: int = Field(..., description="Number of users skipped")


# ============================================================
# JWT Payload Schemas
# ============================================================


class JWTPayloadResponse(BaseModel):
    """
    JWT payload response schema.

    Returns the decoded JWT token payload for debugging/verification.
    """

    user_id: str = Field(..., description="User ID from token")
    email: str | None = Field(None, description="Email from token")
    name: str | None = Field(None, description="Name from token")
    role: str = Field(..., description="Role from token")
    exp: int | None = Field(None, description="Token expiration timestamp")
    iat: int | None = Field(None, description="Token issued at timestamp")
    jti: str | None = Field(None, description="JWT ID")


# ============================================================
# Health/Status Schemas
# ============================================================


class AuthStatusResponse(BaseModel):
    """
    Authentication status response.

    Used for checking if the user is authenticated.
    """

    authenticated: bool = Field(..., description="Whether user is authenticated")
    user_id: str | None = Field(None, description="User ID if authenticated")
    role: str | None = Field(None, description="User role if authenticated")


class HealthResponse(BaseModel):
    """
    Health check response for auth endpoints.
    """

    status: str = Field(..., description="Service status")
    auth_configured: bool = Field(..., description="Whether AUTH_SECRET is configured")
    database_connected: bool = Field(..., description="Whether database is accessible")


class UserValidationResponse(BaseModel):
    """
    User validation response.

    Returns whether the user exists in the database.
    """

    user_id: str = Field(..., description="User ID that was validated")
    exists_in_database: bool = Field(..., description="Whether user exists in DB")
    message: str = Field(..., description="Human-readable message")
