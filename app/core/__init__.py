"""
Core infrastructure components.

- config: Application settings
- database: Database connection and session
- lifespan: App startup/shutdown events
"""

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine, get_db

__all__ = [
    "settings",
    "Base",
    "engine",
    "AsyncSessionLocal",
    "get_db",
]
