"""
API v1 router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.post import router as post_router
from app.api.v1.comment import router as comment_router
from app.api.v1.media import router as media_router
from app.api.v1.poll import router as poll_router

api_router = APIRouter()

# Auth 모듈 (OAuth + JWT)
api_router.include_router(auth_router)     # prefix는 controller에서 정의: /auth

# Post 모듈 (완전 독립)
api_router.include_router(post_router)      # prefix는 controller에서 정의: /posts

# Comment 모듈 (완전 독립 - Post와 별개의 경로)
api_router.include_router(comment_router)   # prefix는 controller에서 정의: /comments

# Media 모듈 (S3 presigned URL 생성)
api_router.include_router(media_router)     # prefix는 controller에서 정의: /media

# Poll 모듈 (여론조사)
api_router.include_router(poll_router)      # prefix는 controller에서 정의: /polls

# Admin 모듈 (관리자 전용)
api_router.include_router(admin_router)     # prefix는 controller에서 정의: /admin
