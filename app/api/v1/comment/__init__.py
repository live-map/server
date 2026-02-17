"""
Comment Module - Nested comments feature module.

This module follows a NestJS-like structure where all related components
(controller, service, repository, schemas) are grouped together.

Structure:
- controller.py           : Comment API route handlers
- service.py              : Comment business logic layer
- repository.py           : Comment data access layer
- dto/schemas.py          : Comment Pydantic schemas
- dto/commentTreeNode.py  : Tree structure DTO
"""

from app.api.v1.comment.controller import router

__all__ = ["router"]