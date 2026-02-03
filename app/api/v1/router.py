"""
API v1 router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.routes.agent import router as agent_router
from app.api.v1.routes.feeds import router as feeds_router
from app.api.v1.post import router as post_router
from app.api.v1.comment import router as comment_router
from app.api.v1.media import router as media_router

api_router = APIRouter()

# Include all routers
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])

# Post 모듈 (완전 독립)
api_router.include_router(post_router)      # prefix는 controller에서 정의: /posts

# Comment 모듈 (완전 독립 - Post와 별개의 경로)
api_router.include_router(comment_router)   # prefix는 controller에서 정의: /comments

# Media 모듈 (S3 presigned URL 생성)
api_router.include_router(media_router)     # prefix는 controller에서 정의: /media