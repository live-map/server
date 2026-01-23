"""
API v1 router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.routes.agent import router as agent_router
from app.api.v1.routes.feeds import router as feeds_router
from app.api.v1.jwt_test import router as jwt_test_router
from app.api.v1.post import router as post_router
from app.api.v1.comment import router as comment_router

api_router = APIRouter()

# Include all routers
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(jwt_test_router, prefix="/jwt-test", tags=["jwt-test", "auth"])

# Post 모듈 (완전 독립)
api_router.include_router(post_router)      # prefix는 controller에서 정의: /posts

# Comment 모듈 (완전 독립 - Post와 별개의 경로)
api_router.include_router(comment_router)   # prefix는 controller에서 정의: /comments