"""
Currents API Trigger

News aggregation API for cross-verification.

Features:
- 1,000 free requests per day
- Multiple categories and languages
- Keyword search
- Region filtering

Reference: https://currentsapi.services/en
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource
from .date_extractor import validate_trigger_recency

logger = logging.getLogger(__name__)

# Currents API endpoint
CURRENTS_API_BASE = "https://api.currentsapi.services/v1"
CURRENTS_SEARCH_URL = f"{CURRENTS_API_BASE}/search"
CURRENTS_LATEST_URL = f"{CURRENTS_API_BASE}/latest-news"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400


class CurrentsTrigger(BaseTrigger):
    """
    Currents API News Trigger

    Tier-2 news source for cross-verification.
    Free tier: 1,000 requests/day
    """

    def __init__(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        language: str = "en",
        country: str | None = None,
        category: str | None = None,
        max_results: int = 50,
        max_age_hours: int = 48,
    ):
        super().__init__(keywords)
        self.api_key = api_key
        self.language = language
        self.country = country
        self.category = category
        self.max_results = max_results
        self.max_age_hours = max_age_hours
        self.seen_hashes: dict[str, float] = {}
        self._request_count = 0

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.CURRENTS

    @property
    def source_name(self) -> str:
        return "Currents API"

    async def initialize(self) -> bool:
        """Validate API key"""
        if not self.api_key:
            logger.warning("Currents API key not configured")
            return False

        self.is_initialized = True
        logger.info("Currents API trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Search Currents API for news

        Searches by keywords and retrieves latest news.
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        if not self.api_key:
            logger.warning("Currents API key not set, skipping scan")
            return events

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search for each keyword
                for keyword in self.keywords[:5]:  # Limit to save API quota
                    if self._request_count >= 900:  # Leave buffer for daily limit
                        logger.warning("Currents API daily limit approaching")
                        break

                    try:
                        response = await client.get(
                            CURRENTS_SEARCH_URL,
                            params={
                                "apiKey": self.api_key,
                                "keywords": keyword,
                                "language": self.language,
                                "country": self.country,
                                "category": self.category,
                            },
                            headers={
                                "Accept": "application/json",
                            },
                        )
                        self._request_count += 1

                        if response.status_code == 429:
                            logger.warning("Currents API rate limit reached")
                            break

                        if response.status_code != 200:
                            logger.warning(f"Currents API error: {response.status_code}")
                            continue

                        data = response.json()
                        news = data.get("news", [])

                        for article in news[:self.max_results]:
                            event = self._parse_article(article, keyword, current_time)
                            if event:
                                events.append(event)

                    except Exception as e:
                        logger.error(f"Currents API search error for '{keyword}': {e}")
                        continue

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(f"Currents API scan: {len(events)} new articles found")

        except Exception as e:
            logger.error(f"Currents API scan error: {e}")

        return events

    def _parse_article(
        self, article: dict[str, Any], keyword: str, current_time: float
    ) -> TriggerEvent | None:
        """Parse a Currents API article into a TriggerEvent"""
        try:
            title = article.get("title", "")
            url = article.get("url", "")

            if not title or not url:
                return None

            # Deduplication
            content_hash = hashlib.md5(f"{url}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Extract fields
            description = article.get("description", "")
            published = article.get("published", "")
            author = article.get("author", "")
            image = article.get("image", "")
            language = article.get("language", self.language)
            category = article.get("category", [])

            # Parse API timestamp
            try:
                api_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                api_date = None

            # Validate recency using 4-Layer validation
            is_recent, reason, validated_date = validate_trigger_recency(
                url=url,
                title=title,
                content=description[:500],
                api_date=api_date,
                max_age_hours=self.max_age_hours,
            )

            if not is_recent:
                logger.info(f"[CURRENTS-RECENCY] Rejected: {reason} | {title[:50]}...")
                return None

            # Use validated date
            detected_at = validated_date if validated_date else datetime.utcnow()

            # Find matched keywords
            full_text = f"{title} {description}"
            matched = self._matches_keywords(full_text)
            if not matched:
                matched = [keyword]

            return TriggerEvent(
                title=title,
                source=TriggerSource.CURRENTS,
                source_name=article.get("id", "currents"),
                url=url,
                detected_at=detected_at,
                content=description,
                language=language,
                keywords_matched=matched,
                media_urls=[image] if image else [],
                author=author,
                raw_data={
                    "id": article.get("id"),
                    "category": category,
                    "source_url": url,
                    "recency_reason": reason,
                },
            )

        except Exception as e:
            logger.error(f"Error parsing Currents article: {e}")
            return None

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes"""
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]
        for h in expired:
            del self.seen_hashes[h]

    def reset_daily_count(self) -> None:
        """Reset daily request count (call at midnight)"""
        self._request_count = 0
        logger.info("Currents API daily request count reset")

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
