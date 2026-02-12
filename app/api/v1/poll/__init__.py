"""
Poll Module - 여론조사 기능 모듈.

Structure:
- controller.py       : Poll API route handlers
- service.py          : Poll business logic layer
- repository.py       : Poll data access layer
- dto/schemas.py      : Poll Pydantic schemas
- vote/               : Vote sub-module
- comment/            : PollComment sub-module
"""

from app.api.v1.poll.controller import router

__all__ = ["router"]
