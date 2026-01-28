"""
Brave Search News Trigger

High-quality news search for initial scan.

Features:
- 2,000 free requests per month (~66/day)
- High-quality news results
- Recent news filtering

Reference: https://brave.com/search/api/
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource
from .date_extractor import validate_trigger_recency
from ..source_tiers import is_trusted_domain
from ..config import agent_settings

logger = logging.getLogger(__name__)

# Brave Search API endpoint
BRAVE_NEWS_URL = "https://api.search.brave.com/res/v1/news/search"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400

# Daily limit (2000/month = ~66/day, use 60 to be safe)
DAILY_LIMIT = 60


class BraveTrigger(BaseTrigger):
    """
    Brave Search News Trigger

    Tier-2 news source for initial scan.
    Free tier: 2,000 requests/month (~66/day)
    """

    def __init__(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        max_results: int = 20,
        max_age_hours: int = 1,  # Match other triggers for consistency
        freshness: str = "pd",  # past day
    ):
        super().__init__(keywords)
        self.api_key = api_key
        self.max_results = max_results
        self.max_age_hours = max_age_hours
        self.freshness = freshness
        self.seen_hashes: dict[str, float] = {}
        self._request_count = 0
        self._last_reset = datetime.utcnow().date()

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.BRAVE

    @property
    def source_name(self) -> str:
        return "Brave Search"

    async def initialize(self) -> bool:
        """Validate API key"""
        if not self.api_key:
            logger.warning("Brave API key not configured")
            return False

        self.is_initialized = True
        logger.info("Brave Search trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Search Brave News API

        Searches combined keywords to save API quota.
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        if not self.api_key:
            logger.warning("Brave API key not set, skipping scan")
            return events

        # Reset daily count if new day
        today = datetime.utcnow().date()
        if today != self._last_reset:
            self._request_count = 0
            self._last_reset = today

        # Check daily limit
        if self._request_count >= DAILY_LIMIT:
            logger.warning("Brave API daily limit reached")
            return events

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Combine keywords into single query to save API quota
                # Use top 5 keywords joined with OR
                query = " OR ".join(self.keywords[:5])

                try:
                    response = await client.get(
                        BRAVE_NEWS_URL,
                        params={
                            "q": query,
                            "count": self.max_results,
                            "freshness": self.freshness,
                        },
                        headers={
                            "Accept": "application/json",
                            "X-Subscription-Token": self.api_key,
                        },
                    )
                    self._request_count += 1

                    if response.status_code == 429:
                        logger.warning("Brave API rate limit reached")
                        return events

                    if response.status_code != 200:
                        logger.warning(f"Brave API error: {response.status_code}")
                        return events

                    data = response.json()
                    results = data.get("results", [])

                    for article in results:
                        event = self._parse_article(article, current_time)
                        if event:
                            events.append(event)

                except Exception as e:
                    logger.error(f"Brave API search error: {e}")

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(f"Brave Search scan: {len(events)} new articles found")

        except Exception as e:
            logger.error(f"Brave Search scan error: {e}")

        return events

    def _parse_article(
        self, article: dict[str, Any], current_time: float
    ) -> TriggerEvent | None:
        """Parse a Brave Search article into a TriggerEvent"""
        try:
            title = article.get("title", "")
            url = article.get("url", "")

            if not title or not url:
                return None

            # Domain whitelist filter (Tier-1/2 only)
            if agent_settings.domain_whitelist_enabled:
                try:
                    domain = urlparse(url).netloc.lower()
                    if domain.startswith("www."):
                        domain = domain[4:]
                except Exception:
                    domain = ""

                if not is_trusted_domain(domain):
                    logger.debug(f"[BRAVE-DOMAIN] Rejected untrusted: {domain}")
                    return None

            # Deduplication
            content_hash = hashlib.md5(f"{url}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Extract fields
            description = article.get("description", "")
            age = article.get("age", "")  # Brave provides relative age like "2 hours ago"

            # Validate recency using 4-Layer validation
            is_recent, reason, validated_date = validate_trigger_recency(
                url=url,
                title=title,
                content=description[:500],
                api_date=None,  # Brave doesn't provide exact timestamp
                max_age_hours=self.max_age_hours,
            )

            if not is_recent:
                logger.info(f"[BRAVE-RECENCY] Rejected: {reason} | {title[:50]}...")
                return None

            # Use validated date
            detected_at = validated_date if validated_date else datetime.utcnow()

            # Find matched keywords
            full_text = f"{title} {description}"
            matched = self._matches_keywords(full_text)
            if not matched:
                # If no explicit keyword match, use first keyword as default
                matched = [self.keywords[0]] if self.keywords else ["news"]

            # Extract domain for source name
            try:
                domain = urlparse(url).netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = "brave"

            return TriggerEvent(
                title=title,
                source=TriggerSource.BRAVE,
                source_name=f"Brave:{domain}",
                url=url,
                detected_at=detected_at,
                content=description,
                language="en",
                keywords_matched=matched,
                media_urls=[],
                author="",
                raw_data={
                    "age": age,
                    "source_url": url,
                    "recency_reason": reason,
                },
            )

        except Exception as e:
            logger.error(f"Error parsing Brave article: {e}")
            return None

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes"""
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]
        for h in expired:
            del self.seen_hashes[h]

    def get_remaining_quota(self) -> int:
        """Get remaining daily quota"""
        return max(0, DAILY_LIMIT - self._request_count)

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
