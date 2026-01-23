# Trigger Implementation Guide

This guide explains how to add a new data source (trigger) to the LiveMap system.

## Overview

Triggers are data source connectors that scan external APIs for news events. Each trigger:
- Inherits from `BaseTrigger`
- Implements async `scan()` to fetch events
- Returns `TriggerEvent` objects
- Has a source tier for confidence scoring

## Step 1: Create Trigger Class

Create a new file in `app/agent/triggers/`:

```python
# app/agent/triggers/newsapi.py
"""
NewsAPI Trigger - Secondary news aggregation
Tier-2: tier2_news (0.75 credibility)
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource, SourceTier

logger = logging.getLogger(__name__)


class NewsAPITrigger(BaseTrigger):
    """
    NewsAPI trigger for news aggregation.

    API Docs: https://newsapi.org/docs
    """

    def __init__(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        language: str = "en",
        page_size: int = 50,
    ):
        super().__init__(keywords=keywords)
        self.api_key = api_key
        self.language = language
        self.page_size = page_size
        self._client: httpx.AsyncClient | None = None

    @property
    def source_type(self) -> TriggerSource:
        """Return the source enum value."""
        # Add to TriggerSource enum first (see Step 2)
        return TriggerSource.NEWSAPI

    @property
    def source_name(self) -> str:
        """Human-readable source name."""
        return "NewsAPI"

    async def initialize(self) -> bool:
        """
        Initialize HTTP client and verify API key.

        Returns:
            True if initialization successful
        """
        try:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"X-Api-Key": self.api_key}
            )

            # Verify API key with a test request
            response = await self._client.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "pageSize": 1}
            )

            if response.status_code == 401:
                logger.error("NewsAPI: Invalid API key")
                return False

            self.is_initialized = True
            logger.info("NewsAPI trigger initialized")
            return True

        except Exception as e:
            logger.error(f"NewsAPI initialization failed: {e}")
            return False

    async def scan(self) -> list[TriggerEvent]:
        """
        Scan NewsAPI for matching articles.

        Returns:
            List of TriggerEvent objects
        """
        if not self.is_initialized or not self._client:
            logger.warning("NewsAPI not initialized, skipping scan")
            return []

        events: list[TriggerEvent] = []
        self.last_scan = datetime.utcnow()

        try:
            # Build query from keywords
            query = " OR ".join(self.keywords)

            response = await self._client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": self.language,
                    "pageSize": self.page_size,
                    "sortBy": "publishedAt",
                }
            )

            if response.status_code != 200:
                logger.warning(f"NewsAPI error: {response.status_code}")
                return []

            data = response.json()
            articles = data.get("articles", [])

            for article in articles:
                event = self._parse_article(article)
                if event:
                    events.append(event)

            logger.info(f"NewsAPI scan complete: {len(events)} events")
            return events

        except Exception as e:
            logger.error(f"NewsAPI scan error: {e}")
            return []

    def _parse_article(self, article: dict) -> TriggerEvent | None:
        """Parse NewsAPI article to TriggerEvent."""
        title = article.get("title", "")
        if not title:
            return None

        # Check keyword match
        text = f"{title} {article.get('description', '')}"
        keywords_matched = self._matches_keywords(text)
        if not keywords_matched:
            return None

        # Parse published date
        published = article.get("publishedAt", "")
        try:
            detected_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            detected_at = datetime.utcnow()

        return TriggerEvent(
            title=title,
            source=self.source_type,
            source_name=article.get("source", {}).get("name", "NewsAPI"),
            url=article.get("url", ""),
            detected_at=detected_at,
            content=article.get("description", ""),
            language=self.language,
            author=article.get("author", ""),
            raw_data=article,
            keywords_matched=keywords_matched,
        )

    async def close(self):
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

## Step 2: Add Source Enum

Add to `app/agent/triggers/base.py`:

```python
class TriggerSource(str, Enum):
    # Existing sources...
    NEWSAPI = "newsapi"  # Add this


# Add tier mapping
SOURCE_TIER_MAP = {
    # Existing mappings...
    TriggerSource.NEWSAPI: SourceTier.TIER2_NEWS,  # Add this
}
```

## Step 3: Register with TriggerManager

Update `app/agent/triggers/manager.py`:

```python
from .newsapi import NewsAPITrigger


class TriggerManager:
    # ... existing code ...

    def add_newsapi(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        language: str = "en",
    ) -> "TriggerManager":
        """Add NewsAPI trigger."""
        trigger = NewsAPITrigger(
            api_key=api_key,
            keywords=keywords,
            language=language,
        )
        self.triggers.append(trigger)
        return self
```

## Step 4: Add Configuration

Update `app/agent/config.py`:

```python
class AgentSettings(BaseSettings):
    # ... existing settings ...

    # NewsAPI
    newsapi_enabled: bool = False
    newsapi_api_key: str = ""
    newsapi_language: str = "en"
```

## Step 5: Integrate in Scanner

Update `app/agent/scanner.py`:

```python
def _create_trigger_manager(self) -> TriggerManager:
    manager = TriggerManager(...)

    # ... existing triggers ...

    # NewsAPI (Tier-2)
    if agent_settings.newsapi_enabled and agent_settings.newsapi_api_key:
        manager.add_newsapi(
            api_key=agent_settings.newsapi_api_key,
            language=agent_settings.newsapi_language,
        )
        logger.info("NewsAPI trigger added (Tier-2)")

    return manager
```

## Step 6: Write Tests

Create `tests/unit/test_trigger_newsapi.py`:

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.triggers.newsapi import NewsAPITrigger
from app.agent.triggers.base import TriggerSource, SourceTier


class TestNewsAPITrigger:
    """Tests for NewsAPI trigger."""

    def test_source_type(self):
        """Source type should be NEWSAPI."""
        trigger = NewsAPITrigger(api_key="test")
        assert trigger.source_type == TriggerSource.NEWSAPI

    def test_source_tier(self):
        """Source tier should be TIER2_NEWS."""
        trigger = NewsAPITrigger(api_key="test")
        assert trigger.source_tier == SourceTier.TIER2_NEWS

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Initialize should return True with valid API key."""
        trigger = NewsAPITrigger(api_key="valid_key")

        with patch.object(trigger, '_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)

            trigger._client = mock_client
            trigger.is_initialized = True

            # Verify initialization would succeed
            assert trigger.is_initialized

    @pytest.mark.asyncio
    async def test_scan_returns_events(self):
        """Scan should return TriggerEvent list."""
        trigger = NewsAPITrigger(api_key="test", keywords=["attack"])
        trigger.is_initialized = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [{
                "title": "Attack reported in region",
                "url": "https://example.com/article",
                "publishedAt": "2024-01-20T10:00:00Z",
                "description": "Details about the attack",
                "source": {"name": "Test Source"},
            }]
        }

        trigger._client = MagicMock()
        trigger._client.get = AsyncMock(return_value=mock_response)

        events = await trigger.scan()

        assert len(events) == 1
        assert events[0].title == "Attack reported in region"
        assert events[0].source == TriggerSource.NEWSAPI
```

## Trigger Checklist

- [ ] Inherit from `BaseTrigger`
- [ ] Implement `source_type` property (add to enum)
- [ ] Implement `source_name` property
- [ ] Implement `initialize()` method
- [ ] Implement `scan()` method
- [ ] Implement `close()` method
- [ ] Add to `SOURCE_TIER_MAP` with appropriate tier
- [ ] Add to `TriggerManager` with `add_xxx()` method
- [ ] Add configuration in `AgentSettings`
- [ ] Integrate in `MultiSourceScanner`
- [ ] Write unit tests
- [ ] Document API limits and rate limiting

## Best Practices

1. **Rate Limiting**: Respect API rate limits
2. **Error Handling**: Log errors, return empty list on failure
3. **Keyword Filtering**: Filter in `scan()` to reduce processing
4. **Timeout Handling**: Use reasonable HTTP timeouts
5. **Resource Cleanup**: Properly close connections in `close()`
