"""
Post Module - Bulletin board feature module.

This module follows a NestJS-like structure where all related components
(controller, service, repository, schemas) are grouped together.

Structure:
- controller.py       : Post API route handlers
- service.py          : Post business logic layer
- repository.py       : Post data access layer
- dto/schemas.py      : Post Pydantic schemas
"""

from app.api.v1.post.controller import router

__all__ = ["router"]