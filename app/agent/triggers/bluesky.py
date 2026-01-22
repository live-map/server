"""
Bluesky Firehose Trigger

Real-time monitoring of Bluesky social network for breaking news signals.

Features:
- AT Protocol Firehose integration
- Keyword-based filtering
- Engagement tracking (likes, reposts)
- Decentralized social network signals

Reference: https://docs.bsky.app/docs/advanced-guides/firehose
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# Bluesky API endpoints
BLUESKY_API_BASE = "https://public.api.bsky.app"
BLUESKY_SEARCH_POSTS = f"{BLUESKY_API_BASE}/xrpc/app.bsky.feed.searchPosts"

# Hash expiry for deduplication
HASH_EXPIRY_SECONDS = 86400


class BlueskyTrigger(BaseTrigger):
    """
    Bluesky Social Network Trigger

    Monitors Bluesky for breaking news signals through:
    - Keyword search in posts
    - Engagement velocity tracking
    - Repost propagation
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        max_results: int = 50,
        min_likes: int = 0,
        min_reposts: int = 0,
    ):
        super().__init__(keywords)
        self.max_results = max_results
        self.min_likes = min_likes
        self.min_reposts = min_reposts
        self.seen_hashes: dict[str, float] = {}

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.BLUESKY

    @property
    def source_name(self) -> str:
        return "Bluesky"

    async def initialize(self) -> bool:
        """Bluesky public API requires no authentication"""
        self.is_initialized = True
        logger.info("Bluesky trigger initialized (public API)")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Search Bluesky posts for keywords

        Uses the public searchPosts endpoint to find relevant posts.
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search for each keyword
                for keyword in self.keywords[:10]:  # Limit to avoid rate limits
                    try:
                        response = await client.get(
                            BLUESKY_SEARCH_POSTS,
                            params={
                                "q": keyword,
                                "limit": min(self.max_results, 100),
                                "sort": "latest",
                            },
                            headers={
                                "Accept": "application/json",
                            },
                        )

                        if response.status_code == 429:
                            logger.warning("Bluesky rate limit reached")
                            break

                        if response.status_code != 200:
                            logger.warning(f"Bluesky search failed for '{keyword}': {response.status_code}")
                            continue

                        data = response.json()
                        posts = data.get("posts", [])

                        for post in posts:
                            event = self._parse_post(post, keyword, current_time)
                            if event:
                                events.append(event)

                    except Exception as e:
                        logger.error(f"Bluesky search error for '{keyword}': {e}")
                        continue

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(f"Bluesky scan: {len(events)} new posts found")

        except Exception as e:
            logger.error(f"Bluesky scan error: {e}")

        return events

    def _parse_post(
        self, post: dict[str, Any], keyword: str, current_time: float
    ) -> TriggerEvent | None:
        """Parse a Bluesky post into a TriggerEvent"""
        try:
            # Extract post data
            record = post.get("record", {})
            text = record.get("text", "")
            uri = post.get("uri", "")
            author = post.get("author", {})

            # Skip if no text
            if not text:
                return None

            # Deduplication
            content_hash = hashlib.md5(f"{uri}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Extract engagement metrics
            like_count = post.get("likeCount", 0)
            repost_count = post.get("repostCount", 0)
            reply_count = post.get("replyCount", 0)

            # Apply engagement filters
            if like_count < self.min_likes or repost_count < self.min_reposts:
                return None

            # Find matched keywords
            matched = self._matches_keywords(text)
            if not matched:
                matched = [keyword]

            # Extract timestamp
            created_at = record.get("createdAt", "")
            try:
                detected_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                detected_at = datetime.utcnow()

            # Extract media URLs if any
            media_urls = []
            embed = post.get("embed", {})
            if embed.get("$type") == "app.bsky.embed.images#view":
                for image in embed.get("images", []):
                    if "fullsize" in image:
                        media_urls.append(image["fullsize"])

            # Build post URL
            author_handle = author.get("handle", "unknown")
            post_id = uri.split("/")[-1] if "/" in uri else uri
            post_url = f"https://bsky.app/profile/{author_handle}/post/{post_id}"

            return TriggerEvent(
                title=text[:200] + "..." if len(text) > 200 else text,
                source=TriggerSource.BLUESKY,
                source_name=f"@{author_handle}",
                url=post_url,
                detected_at=detected_at,
                content=text,
                language=record.get("langs", ["en"])[0] if record.get("langs") else "en",
                keywords_matched=matched,
                media_urls=media_urls,
                author=author.get("displayName", author_handle),
                engagement={
                    "likes": like_count,
                    "reposts": repost_count,
                    "replies": reply_count,
                },
                raw_data=post,
            )

        except Exception as e:
            logger.error(f"Error parsing Bluesky post: {e}")
            return None

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes"""
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]
        for h in expired:
            del self.seen_hashes[h]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired Bluesky hashes")

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
