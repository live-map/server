"""
JWT Test Module - User authentication feature module.

This module follows a NestJS-like structure where all related components
(controller, service, repository, schemas) are grouped together.

Structure:
- controller.py  : API route handlers (like NestJS controllers)
- service.py     : Business logic layer (like NestJS services)
- repository.py  : Data access layer (like NestJS repositories)
- schemas.py     : Pydantic schemas for request/response validation
"""

from app.api.v1.jwt_test.controller import router

__all__ = ["router"]
