"""
API v1 router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.routes.agent import router as agent_router
from app.api.v1.routes.collector import router as collector_router
from app.api.v1.routes.feeds import router as feeds_router
from app.api.v1.routes.verify import router as verify_router

api_router = APIRouter()

# Include all routers
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(verify_router, prefix="/verify", tags=["verify"])
api_router.include_router(collector_router, prefix="/collector", tags=["collector"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
