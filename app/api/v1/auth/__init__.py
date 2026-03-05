"""Auth module - OAuth login, token management, JWT guards."""

from app.api.v1.auth.controller import router
from app.api.v1.auth.jwt_guard import (
    CurrentAdmin,
    CurrentUser,
    CurrentUserOptional,
    JWTPayload,
    get_current_admin,
    get_current_user,
    get_current_user_optional,
)

__all__ = [
    "router",
    "JWTPayload",
    "get_current_user",
    "get_current_user_optional",
    "get_current_admin",
    "CurrentUser",
    "CurrentUserOptional",
    "CurrentAdmin",
]
