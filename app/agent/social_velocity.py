"""
Social Velocity Calculator

Calculates the "velocity" of topics spreading across social platforms.
High velocity indicates potential breaking news.

Velocity Score (0-100):
- < 20: Normal (ignore)
- 20-50: Emerging (monitor)
- 50-80: Trending (start news verification)
- > 80: Viral (immediate verification)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .triggers.base import TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)


@dataclass
class VelocityScore:
    """Social velocity score for a topic"""
    topic: str
    total_score: float  # 0-100
    status: str  # normal, emerging, trending, viral

    # Component scores
    reddit_score: float = 0.0
    bluesky_score: float = 0.0
    telegram_score: float = 0.0
    trends_score: float = 0.0

    # Metrics
    total_mentions: int = 0
    total_engagement: int = 0
    source_count: int = 0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)

    # Source events
    events: list[TriggerEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "total_score": self.total_score,
            "status": self.status,
            "components": {
                "reddit": self.reddit_score,
                "bluesky": self.bluesky_score,
                "telegram": self.telegram_score,
                "google_trends": self.trends_score,
            },
            "metrics": {
                "total_mentions": self.total_mentions,
                "total_engagement": self.total_engagement,
                "source_count": self.source_count,
            },
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


class SocialVelocityCalculator:
    """
    Calculates social velocity scores for topics

    Aggregates signals from:
    - Reddit (upvotes, comments, crossposts)
    - Bluesky (likes, reposts)
    - Telegram (message count, channel spread)
    - Google Trends (breakout detection)
    """

    # Source weights for velocity calculation
    WEIGHTS = {
        "reddit": 0.25,
        "bluesky": 0.15,
        "telegram": 0.30,
        "google_trends": 0.30,
    }

    # Velocity thresholds
    THRESHOLD_VIRAL = 80
    THRESHOLD_TRENDING = 50
    THRESHOLD_EMERGING = 20

    def __init__(self):
        # Topic tracking: topic -> list of events with timestamps
        self.topic_events: dict[str, list[dict]] = {}
        # Cache for velocity scores
        self.velocity_cache: dict[str, VelocityScore] = {}
        # Cleanup interval
        self.cache_ttl = timedelta(hours=6)
        # P0 Fix: Track events added for periodic cleanup
        self._events_since_cleanup = 0
        self._cleanup_threshold = 1000  # Cleanup every 1000 events

    def add_events(self, events: list[TriggerEvent]) -> None:
        """Add new events to tracking"""
        for event in events:
            # Extract topic from event
            topics = self._extract_topics(event)

            for topic in topics:
                if topic not in self.topic_events:
                    self.topic_events[topic] = []

                self.topic_events[topic].append({
                    "event": event,
                    "timestamp": event.detected_at,
                    "source": event.source,
                })

        # P0 Fix: Periodic cleanup to prevent memory leak
        self._events_since_cleanup += len(events)
        if self._events_since_cleanup >= self._cleanup_threshold:
            self.cleanup_old_events()
            self._events_since_cleanup = 0

    def calculate_velocity(self, topic: str) -> VelocityScore:
        """Calculate velocity score for a specific topic"""
        events = self.topic_events.get(topic, [])

        if not events:
            return VelocityScore(
                topic=topic,
                total_score=0.0,
                status="normal",
            )

        # Filter to recent events (last 15 minutes for velocity)
        recent_cutoff = datetime.utcnow() - timedelta(minutes=15)
        recent_events = [
            e for e in events
            if e["timestamp"] >= recent_cutoff
        ]

        # Calculate component scores
        reddit_score = self._calculate_reddit_score(recent_events)
        bluesky_score = self._calculate_bluesky_score(recent_events)
        telegram_score = self._calculate_telegram_score(recent_events)
        trends_score = self._calculate_trends_score(recent_events)

        # Calculate weighted total
        total_score = (
            reddit_score * self.WEIGHTS["reddit"] +
            bluesky_score * self.WEIGHTS["bluesky"] +
            telegram_score * self.WEIGHTS["telegram"] +
            trends_score * self.WEIGHTS["google_trends"]
        )

        # Determine status
        if total_score >= self.THRESHOLD_VIRAL:
            status = "viral"
        elif total_score >= self.THRESHOLD_TRENDING:
            status = "trending"
        elif total_score >= self.THRESHOLD_EMERGING:
            status = "emerging"
        else:
            status = "normal"

        # Calculate metrics
        total_mentions = len(events)
        total_engagement = sum(
            self._get_engagement(e["event"]) for e in events
        )
        sources = set(e["source"] for e in events)

        # Get time range
        timestamps = [e["timestamp"] for e in events]
        first_seen = min(timestamps) if timestamps else datetime.utcnow()
        last_seen = max(timestamps) if timestamps else datetime.utcnow()

        return VelocityScore(
            topic=topic,
            total_score=total_score,
            status=status,
            reddit_score=reddit_score,
            bluesky_score=bluesky_score,
            telegram_score=telegram_score,
            trends_score=trends_score,
            total_mentions=total_mentions,
            total_engagement=total_engagement,
            source_count=len(sources),
            first_seen=first_seen,
            last_seen=last_seen,
            events=[e["event"] for e in recent_events],
        )

    def calculate_all_velocities(self) -> list[VelocityScore]:
        """Calculate velocity scores for all tracked topics"""
        scores = []

        for topic in self.topic_events.keys():
            score = self.calculate_velocity(topic)
            if score.total_score > 0:
                scores.append(score)

        # Sort by score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)

        return scores

    def get_trending_topics(self, min_score: float = 50) -> list[VelocityScore]:
        """Get topics with velocity above threshold"""
        all_scores = self.calculate_all_velocities()
        return [s for s in all_scores if s.total_score >= min_score]

    def get_viral_topics(self) -> list[VelocityScore]:
        """Get topics with viral velocity (>80)"""
        return self.get_trending_topics(min_score=self.THRESHOLD_VIRAL)

    def _calculate_reddit_score(self, events: list[dict]) -> float:
        """Calculate Reddit velocity component"""
        reddit_events = [
            e for e in events
            if e["source"] == TriggerSource.REDDIT
        ]

        if not reddit_events:
            return 0.0

        # Factors:
        # - Post count
        # - Total upvotes (score)
        # - Comment velocity
        # - Crossposts

        total_score = 0
        total_comments = 0
        total_crossposts = 0

        for event_data in reddit_events:
            event = event_data["event"]
            engagement = event.engagement or {}
            total_score += engagement.get("score", 0)
            total_comments += engagement.get("comments", 0)
            total_crossposts += engagement.get("crossposts", 0)

        # Normalize to 0-100
        # High velocity: 1000+ upvotes, 100+ comments, or crossposts
        score = 0

        if total_score >= 1000:
            score += 40
        elif total_score >= 500:
            score += 30
        elif total_score >= 100:
            score += 20
        elif total_score >= 10:
            score += 10

        if total_comments >= 100:
            score += 30
        elif total_comments >= 50:
            score += 20
        elif total_comments >= 10:
            score += 10

        if total_crossposts >= 3:
            score += 30
        elif total_crossposts >= 1:
            score += 15

        return min(score, 100)

    def _calculate_bluesky_score(self, events: list[dict]) -> float:
        """Calculate Bluesky velocity component"""
        bluesky_events = [
            e for e in events
            if e["source"] == TriggerSource.BLUESKY
        ]

        if not bluesky_events:
            return 0.0

        # Factors:
        # - Post count
        # - Total likes
        # - Repost velocity

        total_likes = 0
        total_reposts = 0

        for event_data in bluesky_events:
            event = event_data["event"]
            engagement = event.engagement or {}
            total_likes += engagement.get("likes", 0)
            total_reposts += engagement.get("reposts", 0)

        # Normalize to 0-100
        score = 0

        # Post count velocity
        post_count = len(bluesky_events)
        if post_count >= 50:
            score += 40
        elif post_count >= 20:
            score += 30
        elif post_count >= 10:
            score += 20
        elif post_count >= 5:
            score += 10

        # Engagement
        if total_likes >= 500:
            score += 30
        elif total_likes >= 100:
            score += 20
        elif total_likes >= 20:
            score += 10

        if total_reposts >= 100:
            score += 30
        elif total_reposts >= 20:
            score += 20
        elif total_reposts >= 5:
            score += 10

        return min(score, 100)

    def _calculate_telegram_score(self, events: list[dict]) -> float:
        """Calculate Telegram velocity component"""
        telegram_events = [
            e for e in events
            if e["source"] == TriggerSource.TELEGRAM
        ]

        if not telegram_events:
            return 0.0

        # Factors:
        # - Message count
        # - Channel spread

        message_count = len(telegram_events)
        channels = set(e["event"].source_name for e in telegram_events)

        # Normalize to 0-100
        score = 0

        # Message velocity
        if message_count >= 50:
            score += 50
        elif message_count >= 20:
            score += 35
        elif message_count >= 10:
            score += 25
        elif message_count >= 5:
            score += 15

        # Channel spread
        if len(channels) >= 5:
            score += 50
        elif len(channels) >= 3:
            score += 35
        elif len(channels) >= 2:
            score += 20

        return min(score, 100)

    def _calculate_trends_score(self, events: list[dict]) -> float:
        """Calculate Google Trends velocity component"""
        trends_events = [
            e for e in events
            if e["source"] == TriggerSource.GOOGLE_TRENDS
        ]

        if not trends_events:
            return 0.0

        # Factors:
        # - Breakout detection
        # - Trending rank
        # - Interest level

        score = 0

        for event_data in trends_events:
            event = event_data["event"]
            engagement = event.engagement or {}

            # Breakout is highest signal
            if engagement.get("type") == "breakout":
                spike_percent = engagement.get("spike_percent", 0)
                if spike_percent >= 200:
                    score += 80
                elif spike_percent >= 100:
                    score += 60
                elif spike_percent >= 50:
                    score += 40

            # Trending rank
            elif engagement.get("type") == "trending_search":
                rank = engagement.get("rank", 100)
                if rank <= 3:
                    score += 60
                elif rank <= 10:
                    score += 40
                elif rank <= 25:
                    score += 20

            # Interest level
            interest = engagement.get("current_interest", 0)
            if interest >= 80:
                score += 20
            elif interest >= 50:
                score += 10

        return min(score, 100)

    def _extract_topics(self, event: TriggerEvent) -> list[str]:
        """Extract topic keywords from an event"""
        topics = []

        # Use matched keywords
        if event.keywords_matched:
            topics.extend([
                kw for kw in event.keywords_matched
                if not kw.startswith("[")  # Skip markers
            ])

        # Extract from title
        if event.title:
            # Simple extraction: use significant words
            words = event.title.lower().split()
            for word in words:
                if len(word) >= 5 and word.isalpha():
                    topics.append(word)

        return list(set(topics))[:5]  # Limit to 5 topics per event

    def _get_engagement(self, event: TriggerEvent) -> int:
        """Get total engagement count from event"""
        engagement = event.engagement or {}

        total = 0
        total += engagement.get("score", 0)
        total += engagement.get("likes", 0)
        total += engagement.get("reposts", 0)
        total += engagement.get("comments", 0)

        return total

    def cleanup_old_events(self) -> None:
        """Remove events older than cache TTL"""
        cutoff = datetime.utcnow() - self.cache_ttl

        for topic in list(self.topic_events.keys()):
            events = self.topic_events[topic]
            filtered = [
                e for e in events
                if e["timestamp"] >= cutoff
            ]

            if filtered:
                self.topic_events[topic] = filtered
            else:
                del self.topic_events[topic]

        logger.debug(f"Cleaned up old velocity events, {len(self.topic_events)} topics remaining")
