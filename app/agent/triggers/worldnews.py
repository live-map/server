"""
World News API Trigger

Global news API for cross-verification.

Features:
- 500 free requests per day
- Text search with highlighting
- Source filtering
- Entity extraction

Reference: https://worldnewsapi.com/
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

# World News API endpoint
WORLDNEWS_API_BASE = "https://api.worldnewsapi.com"
WORLDNEWS_SEARCH_URL = f"{WORLDNEWS_API_BASE}/search-news"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400


class WorldNewsTrigger(BaseTrigger):
    """
    World News API Trigger

    Tier-2 news source for cross-verification.
    Free tier: 500 requests/day
    """

    def __init__(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        language: str = "en",
        source_countries: str | None = None,
        max_results: int = 50,
        max_age_hours: int = 48,
    ):
        super().__init__(keywords)
        self.api_key = api_key
        self.language = language
        self.source_countries = source_countries
        self.max_results = max_results
        self.max_age_hours = max_age_hours
        self.seen_hashes: dict[str, float] = {}
        self._request_count = 0

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.WORLDNEWS

    @property
    def source_name(self) -> str:
        return "World News API"

    async def initialize(self) -> bool:
        """Validate API key"""
        if not self.api_key:
            logger.warning("World News API key not configured")
            return False

        self.is_initialized = True
        logger.info("World News API trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Search World News API for news

        Searches by text and retrieves relevant articles.
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        if not self.api_key:
            logger.warning("World News API key not set, skipping scan")
            return events

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Build combined search query
                search_text = " OR ".join(self.keywords[:10])

                if self._request_count >= 450:  # Leave buffer for daily limit
                    logger.warning("World News API daily limit approaching")
                    return events

                try:
                    params = {
                        "api-key": self.api_key,
                        "text": search_text,
                        "language": self.language,
                        "number": min(self.max_results, 100),
                        "sort": "publish-time",
                        "sort-direction": "DESC",
                    }

                    if self.source_countries:
                        params["source-countries"] = self.source_countries

                    response = await client.get(
                        WORLDNEWS_SEARCH_URL,
                        params=params,
                        headers={
                            "Accept": "application/json",
                        },
                    )
                    self._request_count += 1

                    if response.status_code == 429:
                        logger.warning("World News API rate limit reached")
                        return events

                    if response.status_code == 401:
                        logger.error("World News API authentication failed")
                        return events

                    if response.status_code != 200:
                        logger.warning(f"World News API error: {response.status_code}")
                        return events

                    data = response.json()
                    news = data.get("news", [])

                    for article in news:
                        event = self._parse_article(article, current_time)
                        if event:
                            events.append(event)

                except Exception as e:
                    logger.error(f"World News API search error: {e}")

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(f"World News API scan: {len(events)} new articles found")

        except Exception as e:
            logger.error(f"World News API scan error: {e}")

        return events

    def _parse_article(
        self, article: dict[str, Any], current_time: float
    ) -> TriggerEvent | None:
        """Parse a World News API article into a TriggerEvent"""
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
            text = article.get("text", "")
            summary = article.get("summary", "")
            publish_date = article.get("publish_date", "")
            author = article.get("author", "")
            image = article.get("image", "")
            language = article.get("language", self.language)
            source_country = article.get("source_country", "")
            sentiment = article.get("sentiment", 0)

            # Parse API timestamp
            try:
                api_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                api_date = None

            # Validate recency using 4-Layer validation
            is_recent, reason, validated_date = validate_trigger_recency(
                url=url,
                title=title,
                content=text[:500] if text else summary[:500],
                api_date=api_date,
                max_age_hours=self.max_age_hours,
            )

            # P0: Date Fallback - Allow API date if within 24 hours
            if not is_recent:
                if "NO_DATE_INFO" in reason and api_date:
                    api_age_hours = (datetime.utcnow() - api_date.replace(tzinfo=None)).total_seconds() / 3600
                    if api_age_hours <= 24:
                        is_recent = True
                        validated_date = api_date.replace(tzinfo=None)
                        reason = f"DATE_FALLBACK: Using API published {api_date.date()} (age: {api_age_hours:.1f}h)"
                        logger.warning(f"[DATE-FALLBACK] {title[:50]}... | {reason}")
                    else:
                        logger.info(f"[WORLDNEWS-RECENCY] Rejected (API date too old): {reason} | {title[:50]}...")
                        return None
                else:
                    logger.info(f"[WORLDNEWS-RECENCY] Rejected: {reason} | {title[:50]}...")
                    return None

            # Use validated date
            detected_at = validated_date if validated_date else datetime.utcnow()

            # Find matched keywords
            full_text = f"{title} {text}"
            matched = self._matches_keywords(full_text)
            if not matched:
                matched = ["[worldnews-search]"]

            # Use summary if available, otherwise truncate text
            content = summary if summary else (text[:500] + "..." if len(text) > 500 else text)

            return TriggerEvent(
                title=title,
                source=TriggerSource.WORLDNEWS,
                source_name=article.get("source", "worldnews"),
                url=url,
                detected_at=detected_at,
                content=content,
                language=language,
                country=source_country,
                keywords_matched=matched,
                media_urls=[image] if image else [],
                author=author,
                raw_data={
                    "id": article.get("id"),
                    "sentiment": sentiment,
                    "category": article.get("category"),
                    "full_text": text,
                    "recency_reason": reason,
                },
            )

        except Exception as e:
            logger.error(f"Error parsing World News article: {e}")
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
        logger.info("World News API daily request count reset")

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
