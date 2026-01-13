"""
API v1 route handlers.

- feeds: Feed CRUD endpoints
- verify: Legacy verification pipeline
- collector: Telegram collector management
- agent: Autonomous investigation agent
"""

from app.api.v1.routes import collector, feeds, verify

__all__ = ["feeds", "verify", "collector"]
