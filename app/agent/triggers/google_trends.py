"""
Google Trends Trigger

Monitors Google Trends for breaking news signals through:
- Real-time trending searches
- Interest spike detection (breakout)
- Related queries analysis

Uses pytrends library for unofficial Google Trends API access.

Reference: https://github.com/GeneralMills/pytrends
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# Google Trends API (unofficial)
TRENDS_API_BASE = "https://trends.google.com"
REALTIME_TRENDS_URL = f"{TRENDS_API_BASE}/trends/trendingsearches/daily/rss"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400


class GoogleTrendsTrigger(BaseTrigger):
    """
    Google Trends Signal Trigger

    Monitors Google Trends for:
    - Real-time trending searches
    - Interest breakouts (100%+ surge)
    - News-related trend spikes
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        geo: str = "US",  # Geographic region
        min_interest: int = 50,  # Minimum interest score (0-100)
    ):
        super().__init__(keywords)
        self.geo = geo
        self.min_interest = min_interest
        self.seen_hashes: dict[str, float] = {}
        self._pytrends = None

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.GOOGLE_TRENDS

    @property
    def source_name(self) -> str:
        return "Google Trends"

    async def initialize(self) -> bool:
        """Initialize pytrends connection"""
        try:
            from pytrends.request import TrendReq
            self._pytrends = TrendReq(hl="en-US", tz=360)
            self.is_initialized = True
            logger.info("Google Trends trigger initialized")
            return True
        except ImportError:
            logger.warning("pytrends not installed, using fallback")
            self.is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Google Trends init error: {e}")
            return False

    async def scan(self) -> list[TriggerEvent]:
        """
        Scan Google Trends for breaking news signals

        1. Get real-time trending searches
        2. Check interest for monitored keywords
        3. Detect breakout patterns
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        try:
            # Get trending searches
            trending_events = await self._get_trending_searches()
            events.extend(trending_events)

            # Check keyword interest if pytrends is available
            if self._pytrends:
                keyword_events = await self._check_keyword_interest()
                events.extend(keyword_events)

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(f"Google Trends scan: {len(events)} new trends found")

        except Exception as e:
            logger.error(f"Google Trends scan error: {e}")

        return events

    async def _get_trending_searches(self) -> list[TriggerEvent]:
        """Get real-time trending searches"""
        events = []
        current_time = time.time()

        try:
            if self._pytrends:
                # Use pytrends for trending searches
                from fastapi.concurrency import run_in_threadpool
                trending_df = await run_in_threadpool(
                    self._pytrends.trending_searches,
                    pn=self.geo.lower()
                )

                for idx, row in trending_df.iterrows():
                    query = str(row[0]) if len(row) > 0 else str(row)

                    # Check if related to our keywords
                    if not self._is_relevant(query):
                        continue

                    # Deduplication
                    content_hash = hashlib.md5(f"trend:{query}:{current_time // 3600}".encode()).hexdigest()
                    if content_hash in self.seen_hashes:
                        continue
                    self.seen_hashes[content_hash] = current_time

                    events.append(TriggerEvent(
                        title=f"Trending: {query}",
                        source=TriggerSource.GOOGLE_TRENDS,
                        source_name=f"Google Trends ({self.geo})",
                        url=f"https://trends.google.com/trends/explore?q={query}&geo={self.geo}",
                        detected_at=datetime.utcnow(),
                        content=f"'{query}' is trending on Google in {self.geo}",
                        language="en",
                        keywords_matched=self._matches_keywords(query) or ["[trending]"],
                        engagement={
                            "rank": idx + 1,
                            "type": "trending_search",
                        },
                        raw_data={
                            "query": query,
                            "geo": self.geo,
                            "trend_type": "realtime",
                        },
                    ))

        except Exception as e:
            logger.error(f"Error getting trending searches: {e}")

        return events

    async def _check_keyword_interest(self) -> list[TriggerEvent]:
        """Check interest levels for monitored keywords"""
        events = []
        current_time = time.time()

        if not self._pytrends or not self.keywords:
            return events

        try:
            from fastapi.concurrency import run_in_threadpool

            # Check keywords in batches of 5 (Google Trends limit)
            for i in range(0, len(self.keywords), 5):
                batch = self.keywords[i:i+5]

                try:
                    # Build payload
                    await run_in_threadpool(
                        self._pytrends.build_payload,
                        batch,
                        timeframe="now 1-H",
                        geo=self.geo
                    )

                    # Get interest over time
                    interest_df = await run_in_threadpool(
                        self._pytrends.interest_over_time
                    )

                    if interest_df.empty:
                        continue

                    # Check for spikes
                    for keyword in batch:
                        if keyword not in interest_df.columns:
                            continue

                        values = interest_df[keyword].values
                        if len(values) < 2:
                            continue

                        current_interest = values[-1]
                        avg_interest = values[:-1].mean() if len(values) > 1 else 0

                        # Detect breakout (100%+ increase)
                        if avg_interest > 0 and current_interest >= avg_interest * 2:
                            # Deduplication
                            content_hash = hashlib.md5(
                                f"breakout:{keyword}:{current_time // 3600}".encode()
                            ).hexdigest()
                            if content_hash in self.seen_hashes:
                                continue
                            self.seen_hashes[content_hash] = current_time

                            events.append(TriggerEvent(
                                title=f"Search Spike: {keyword}",
                                source=TriggerSource.GOOGLE_TRENDS,
                                source_name=f"Google Trends ({self.geo})",
                                url=f"https://trends.google.com/trends/explore?q={keyword}&geo={self.geo}",
                                detected_at=datetime.utcnow(),
                                content=f"'{keyword}' search interest spiked {int((current_interest/avg_interest - 1) * 100)}% in the last hour",
                                language="en",
                                keywords_matched=[keyword],
                                engagement={
                                    "current_interest": int(current_interest),
                                    "avg_interest": int(avg_interest),
                                    "spike_percent": int((current_interest/avg_interest - 1) * 100),
                                    "type": "breakout",
                                },
                                raw_data={
                                    "keyword": keyword,
                                    "geo": self.geo,
                                    "trend_type": "breakout",
                                    "values": values.tolist()[-10:],  # Last 10 values
                                },
                            ))

                except Exception as e:
                    logger.warning(f"Error checking interest for batch {batch}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error checking keyword interest: {e}")

        return events

    def _is_relevant(self, query: str) -> bool:
        """Check if a trending query is relevant to our keywords"""
        query_lower = query.lower()

        # Check for keyword matches
        for keyword in self.keywords:
            if keyword.lower() in query_lower:
                return True

        # News-related patterns
        news_patterns = [
            "breaking", "news", "update", "alert",
            "earthquake", "attack", "explosion", "fire",
            "crash", "protest", "war", "conflict",
        ]

        for pattern in news_patterns:
            if pattern in query_lower:
                return True

        return False

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes"""
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]
        for h in expired:
            del self.seen_hashes[h]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired Google Trends hashes")

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
        self._pytrends = None
