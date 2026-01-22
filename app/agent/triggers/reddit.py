"""
Reddit API Trigger

Monitors Reddit for breaking news signals through:
- News-related subreddits (r/worldnews, r/news, etc.)
- Keyword search across posts
- Upvote velocity tracking
- Cross-post detection

Reference: https://www.reddit.com/dev/api/
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# Reddit API endpoint
REDDIT_API_BASE = "https://www.reddit.com"
REDDIT_SEARCH_API = f"{REDDIT_API_BASE}/search.json"

# News-related subreddits
NEWS_SUBREDDITS = [
    "worldnews",
    "news",
    "UkrainianConflict",
    "geopolitics",
    "breakingnews",
    "worldpolitics",
    "internationalnews",
]

# Hash expiry
HASH_EXPIRY_SECONDS = 86400


class RedditTrigger(BaseTrigger):
    """
    Reddit Social News Trigger

    Monitors Reddit for breaking news signals through:
    - Search across news subreddits
    - Upvote velocity tracking
    - Cross-post propagation
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        subreddits: list[str] | None = None,
        max_results: int = 50,
        min_score: int = 10,  # Minimum upvotes
        min_comments: int = 0,
        time_filter: str = "day",  # hour, day, week, month, year, all
    ):
        super().__init__(keywords)
        self.subreddits = subreddits or NEWS_SUBREDDITS
        self.max_results = max_results
        self.min_score = min_score
        self.min_comments = min_comments
        self.time_filter = time_filter
        self.seen_hashes: dict[str, float] = {}
        # User agent required by Reddit API
        self.user_agent = "LiveMapBot/1.0 (Breaking News Monitor)"

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.REDDIT

    @property
    def source_name(self) -> str:
        return "Reddit"

    async def initialize(self) -> bool:
        """Reddit public API requires no authentication for read-only"""
        self.is_initialized = True
        logger.info("Reddit trigger initialized (public API)")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Search Reddit for breaking news

        1. Search across news subreddits for keywords
        2. Filter by engagement (score, comments)
        3. Track cross-posts for velocity
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Build subreddit filter
                subreddit_filter = "+".join(self.subreddits[:10])

                # Search for each keyword
                for keyword in self.keywords[:10]:
                    try:
                        response = await client.get(
                            f"{REDDIT_API_BASE}/r/{subreddit_filter}/search.json",
                            params={
                                "q": keyword,
                                "sort": "relevance",
                                "t": self.time_filter,
                                "limit": min(self.max_results, 100),
                                "restrict_sr": "on",
                            },
                            headers={
                                "User-Agent": self.user_agent,
                            },
                        )

                        if response.status_code == 429:
                            logger.warning("Reddit rate limit reached")
                            # Wait and retry
                            await self._wait_for_rate_limit()
                            continue

                        if response.status_code != 200:
                            logger.warning(f"Reddit search failed for '{keyword}': {response.status_code}")
                            continue

                        data = response.json()
                        posts = data.get("data", {}).get("children", [])

                        for post_wrapper in posts:
                            post = post_wrapper.get("data", {})
                            event = self._parse_post(post, keyword, current_time)
                            if event:
                                events.append(event)

                    except Exception as e:
                        logger.error(f"Reddit search error for '{keyword}': {e}")
                        continue

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(f"Reddit scan: {len(events)} new posts found")

        except Exception as e:
            logger.error(f"Reddit scan error: {e}")

        return events

    def _parse_post(
        self, post: dict[str, Any], keyword: str, current_time: float
    ) -> TriggerEvent | None:
        """Parse a Reddit post into a TriggerEvent"""
        try:
            # Extract post data
            title = post.get("title", "")
            selftext = post.get("selftext", "")
            permalink = post.get("permalink", "")
            post_id = post.get("id", "")

            # Skip if no title
            if not title:
                return None

            # Deduplication
            content_hash = hashlib.md5(f"{post_id}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Extract engagement metrics
            score = post.get("score", 0)
            num_comments = post.get("num_comments", 0)
            upvote_ratio = post.get("upvote_ratio", 0)
            num_crossposts = post.get("num_crossposts", 0)

            # Apply engagement filters
            if score < self.min_score or num_comments < self.min_comments:
                return None

            # Find matched keywords
            full_text = f"{title} {selftext}"
            matched = self._matches_keywords(full_text)
            if not matched:
                matched = [keyword]

            # Extract timestamp
            created_utc = post.get("created_utc", 0)
            try:
                detected_at = datetime.utcfromtimestamp(created_utc)
            except (ValueError, OSError):
                detected_at = datetime.utcnow()

            # Extract media
            media_urls = []
            if post.get("is_video") and post.get("media"):
                media = post.get("media", {})
                reddit_video = media.get("reddit_video", {})
                if reddit_video.get("fallback_url"):
                    media_urls.append(reddit_video["fallback_url"])
            elif post.get("url") and any(
                ext in post.get("url", "")
                for ext in [".jpg", ".png", ".gif", ".mp4", ".webm"]
            ):
                media_urls.append(post["url"])

            # Build full URL
            post_url = f"https://www.reddit.com{permalink}"

            # Get external link if any
            external_url = post.get("url", "")
            if external_url and not external_url.startswith("https://www.reddit.com"):
                content = f"{selftext}\n\nSource: {external_url}" if selftext else external_url
            else:
                content = selftext

            return TriggerEvent(
                title=title,
                source=TriggerSource.REDDIT,
                source_name=f"r/{post.get('subreddit', 'unknown')}",
                url=post_url,
                detected_at=detected_at,
                content=content,
                language="en",  # Reddit is primarily English
                keywords_matched=matched,
                media_urls=media_urls,
                author=post.get("author", "[deleted]"),
                engagement={
                    "score": score,
                    "comments": num_comments,
                    "upvote_ratio": upvote_ratio,
                    "crossposts": num_crossposts,
                },
                raw_data={
                    "post_id": post_id,
                    "subreddit": post.get("subreddit"),
                    "domain": post.get("domain"),
                    "is_self": post.get("is_self"),
                    "over_18": post.get("over_18"),
                    "spoiler": post.get("spoiler"),
                    "link_flair_text": post.get("link_flair_text"),
                    "external_url": external_url if external_url != post_url else None,
                },
            )

        except Exception as e:
            logger.error(f"Error parsing Reddit post: {e}")
            return None

    async def _wait_for_rate_limit(self):
        """Wait for rate limit to reset"""
        import asyncio
        await asyncio.sleep(60)  # Wait 1 minute

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes"""
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]
        for h in expired:
            del self.seen_hashes[h]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired Reddit hashes")

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
