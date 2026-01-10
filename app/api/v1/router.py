"""
API v1 router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.feeds import router as feeds_router
from app.api.v1.verify import router as verify_router

api_router = APIRouter()

# Include all routers
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(verify_router, prefix="/verify", tags=["verify"])

# Future routers:
# api_router.include_router(channels_router, prefix="/channels", tags=["channels"])
