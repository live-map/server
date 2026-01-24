"""
Breaking News Fast-Path Detection

Implements fast-path processing for breaking news events.
Breaking news can bypass certain verification gates while
maintaining credibility through source tier assessment.

Research basis:
- Reuters Tracer: 27 min faster than CNN/BBC on average
- Twitter anomaly detection patterns
- Volume spike detection algorithms
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from collections import defaultdict

from .source_tiers import (
    DomainTier,
    get_domain_tier,
    is_single_source_allowed,
    normalize_domain,
)

logger = logging.getLogger(__name__)


class BreakingNewsType(str, Enum):
    """Types of breaking news events"""
    KEYWORD_TRIGGERED = "keyword_triggered"  # Breaking keywords in title
    VOLUME_SPIKE = "volume_spike"           # Sudden increase in same topic
    TIER1_EXCLUSIVE = "tier1_exclusive"     # Tier-1 source exclusive
    DEVELOPING_STORY = "developing_story"   # Ongoing development
    FLASH_NEWS = "flash_news"               # Urgent flash from wire service


# Breaking news keywords - case insensitive
BREAKING_KEYWORDS: list[str] = [
    "breaking",
    "just in",
    "urgent",
    "flash",
    "developing",
    "happening now",
    "live updates",
    "breaking news",
    "alert",
]

# Flash news patterns (typically wire services)
FLASH_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bFLASH\s*[:\-]", re.IGNORECASE),
    re.compile(r"\bURGENT\s*[:\-]", re.IGNORECASE),
    re.compile(r"\bBREAKING\s*[:\-]", re.IGNORECASE),
    re.compile(r"\bALERT\s*[:\-]", re.IGNORECASE),
]

# High-urgency event patterns
URGENT_EVENT_PATTERNS: list[re.Pattern] = [
    # Mass casualty events
    re.compile(r"\b(mass\s+shooting|terror\s*attack|explosion|bombing)\b", re.IGNORECASE),
    # Major military actions
    re.compile(r"\b(airstrikes?|missile\s+attack|invasion|troops\s+deployed)\b", re.IGNORECASE),
    # Natural disasters
    re.compile(r"\b(earthquake|tsunami|hurricane|typhoon)\s+(hit|strike|devastate)", re.IGNORECASE),
    # Political crises
    re.compile(r"\b(coup|martial\s+law|state\s+of\s+emergency|assassinat)", re.IGNORECASE),
    # Significant deaths
    re.compile(r"\b(president|prime\s+minister|leader)\s+(dead|dies|killed)\b", re.IGNORECASE),
]


@dataclass
class BreakingNewsResult:
    """Result of breaking news detection"""
    is_breaking: bool
    breaking_type: Optional[BreakingNewsType] = None
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    fast_path_eligible: bool = False
    gates_to_skip: list[str] = field(default_factory=list)
    label: str = ""  # "BREAKING", "DEVELOPING", "FLASH", etc.
    verification_schedule_minutes: int = 30  # Re-verify after N minutes

    def to_dict(self) -> dict:
        return {
            "is_breaking": self.is_breaking,
            "breaking_type": self.breaking_type.value if self.breaking_type else None,
            "confidence": round(self.confidence, 3),
            "signals": self.signals,
            "fast_path_eligible": self.fast_path_eligible,
            "gates_to_skip": self.gates_to_skip,
            "label": self.label,
            "verification_schedule_minutes": self.verification_schedule_minutes,
        }


class BreakingNewsDetector:
    """
    Detects breaking news and determines fast-path eligibility.

    Fast-path processing allows breaking news to skip certain gates:
    - Gate 2 (Specificity): Breaking news may lack specific details initially
    - Gate 3 (Evidence): May not have corroborating evidence yet

    Compensatory measures:
    - "DEVELOPING" label attached to article
    - Automatic re-verification scheduled (default: 30 minutes)
    - Higher source tier requirement for single-source breaking news
    """

    def __init__(
        self,
        volume_spike_threshold: float = 3.0,
        volume_window_minutes: int = 5,
        min_breaking_confidence: float = 0.6,
    ):
        """
        Args:
            volume_spike_threshold: Multiplier for volume spike detection (3x = 3.0)
            volume_window_minutes: Window for volume spike calculation
            min_breaking_confidence: Minimum confidence to classify as breaking
        """
        self.volume_spike_threshold = volume_spike_threshold
        self.volume_window_minutes = volume_window_minutes
        self.min_breaking_confidence = min_breaking_confidence

        # Topic volume tracking (for volume spike detection)
        self._topic_volumes: dict[str, list[datetime]] = defaultdict(list)

    def detect(
        self,
        title: str,
        content: str = "",
        source_url: str = "",
        detected_at: Optional[datetime] = None,
        topic_key: Optional[str] = None,
    ) -> BreakingNewsResult:
        """
        Detect if an article is breaking news.

        Args:
            title: Article title
            content: Article content (optional)
            source_url: Source URL for tier assessment
            detected_at: Detection timestamp
            topic_key: Key for volume tracking (e.g., normalized topic)

        Returns:
            BreakingNewsResult with detection details
        """
        detected_at = detected_at or datetime.utcnow()
        signals: list[str] = []
        confidence = 0.0
        breaking_type = None

        text = f"{title} {content}".lower()

        # 1. Check for breaking keywords in title (highest signal)
        title_lower = title.lower()
        keyword_matches = [kw for kw in BREAKING_KEYWORDS if kw in title_lower]
        if keyword_matches:
            confidence += 0.4
            signals.append(f"Breaking keywords: {', '.join(keyword_matches)}")
            breaking_type = BreakingNewsType.KEYWORD_TRIGGERED

        # 2. Check for flash patterns (wire service style)
        for pattern in FLASH_PATTERNS:
            if pattern.search(title):
                confidence += 0.3
                signals.append(f"Flash pattern detected: {pattern.pattern}")
                breaking_type = BreakingNewsType.FLASH_NEWS
                break

        # 3. Check for urgent event patterns
        for pattern in URGENT_EVENT_PATTERNS:
            if pattern.search(text):
                confidence += 0.2
                signals.append(f"Urgent event pattern: {pattern.pattern}")
                break

        # 4. Check source tier (Tier-1 gets breaking boost)
        if source_url:
            domain_tier = get_domain_tier(source_url)
            if domain_tier == DomainTier.TIER_1:
                confidence += 0.2
                signals.append(f"Tier-1 source: {normalize_domain(source_url)}")
                if not breaking_type:
                    breaking_type = BreakingNewsType.TIER1_EXCLUSIVE

        # 5. Check volume spike (if topic tracking enabled)
        if topic_key:
            is_spike = self._check_volume_spike(topic_key, detected_at)
            if is_spike:
                confidence += 0.3
                signals.append(f"Volume spike detected for topic: {topic_key}")
                if not breaking_type:
                    breaking_type = BreakingNewsType.VOLUME_SPIKE

        # Determine if breaking news
        is_breaking = confidence >= self.min_breaking_confidence

        # Determine fast-path eligibility
        fast_path_eligible = False
        gates_to_skip: list[str] = []
        label = ""
        verification_schedule = 30

        if is_breaking:
            # Breaking news from Tier-1 or Tier-2 sources can skip gates
            if source_url:
                domain_tier = get_domain_tier(source_url)
                if domain_tier in [DomainTier.TIER_1, DomainTier.TIER_2]:
                    fast_path_eligible = True
                    # P1 Fix: High-confidence breaking news can also skip Gate 0
                    if confidence >= 0.8:
                        gates_to_skip = ["gate0_verification", "gate2_specificity", "gate3_evidence"]
                    else:
                        gates_to_skip = ["gate2_specificity", "gate3_evidence"]
                    logger.info(
                        f"[BREAKING] Fast-path enabled: {title[:50]}... "
                        f"(tier={domain_tier.value}, signals={len(signals)}, skip_gates={len(gates_to_skip)})"
                    )

            # Determine label
            if breaking_type == BreakingNewsType.FLASH_NEWS:
                label = "FLASH"
                verification_schedule = 15  # Faster verification for flash
            elif confidence >= 0.8:
                label = "BREAKING"
                verification_schedule = 20
            else:
                label = "DEVELOPING"
                verification_schedule = 30

            logger.info(
                f"[BREAKING] Detected: {label} - {title[:50]}... "
                f"(confidence={confidence:.2f}, type={breaking_type})"
            )

        return BreakingNewsResult(
            is_breaking=is_breaking,
            breaking_type=breaking_type,
            confidence=min(confidence, 1.0),
            signals=signals,
            fast_path_eligible=fast_path_eligible,
            gates_to_skip=gates_to_skip,
            label=label,
            verification_schedule_minutes=verification_schedule,
        )

    def _check_volume_spike(self, topic_key: str, current_time: datetime) -> bool:
        """
        Check if there's a volume spike for a topic.

        Volume spike = 3x normal volume within the window.

        Args:
            topic_key: Normalized topic identifier
            current_time: Current timestamp

        Returns:
            True if volume spike detected
        """
        # Clean old entries
        window_start = current_time - timedelta(minutes=self.volume_window_minutes)
        self._topic_volumes[topic_key] = [
            t for t in self._topic_volumes[topic_key]
            if t > window_start
        ]

        # Add current entry
        self._topic_volumes[topic_key].append(current_time)

        # Check volume
        current_volume = len(self._topic_volumes[topic_key])

        # Need at least 3 articles in window for spike detection
        if current_volume >= 3:
            # Calculate baseline (average volume per window)
            # For simplicity, we use 1 article per window as baseline
            baseline = 1
            spike_threshold = baseline * self.volume_spike_threshold

            if current_volume >= spike_threshold:
                logger.info(
                    f"[VOLUME-SPIKE] Topic '{topic_key}': "
                    f"{current_volume} articles in {self.volume_window_minutes}min "
                    f"(threshold: {spike_threshold})"
                )
                return True

        return False

    def record_topic_occurrence(self, topic_key: str, timestamp: Optional[datetime] = None):
        """
        Record a topic occurrence for volume tracking.

        Args:
            topic_key: Normalized topic identifier
            timestamp: Occurrence timestamp (default: now)
        """
        timestamp = timestamp or datetime.utcnow()
        self._topic_volumes[topic_key].append(timestamp)

    def get_topic_volume(self, topic_key: str, window_minutes: Optional[int] = None) -> int:
        """
        Get current volume for a topic.

        Args:
            topic_key: Normalized topic identifier
            window_minutes: Custom window (default: detector's window)

        Returns:
            Number of occurrences in window
        """
        window_minutes = window_minutes or self.volume_window_minutes
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)

        return len([
            t for t in self._topic_volumes.get(topic_key, [])
            if t > window_start
        ])

    def clear_topic_volumes(self):
        """Clear all topic volume tracking data."""
        self._topic_volumes.clear()


# Convenience function
def is_breaking_news(
    title: str,
    content: str = "",
    source_url: str = "",
) -> bool:
    """
    Quick check if an article is breaking news.

    Args:
        title: Article title
        content: Article content
        source_url: Source URL

    Returns:
        True if breaking news detected
    """
    detector = BreakingNewsDetector()
    result = detector.detect(title, content, source_url)
    return result.is_breaking


def get_breaking_news_label(
    title: str,
    content: str = "",
    source_url: str = "",
) -> str:
    """
    Get the breaking news label if applicable.

    Args:
        title: Article title
        content: Article content
        source_url: Source URL

    Returns:
        Label string ("BREAKING", "DEVELOPING", "FLASH", or "")
    """
    detector = BreakingNewsDetector()
    result = detector.detect(title, content, source_url)
    return result.label


# Global detector instance for volume tracking across calls
_global_detector: Optional[BreakingNewsDetector] = None


def get_global_detector() -> BreakingNewsDetector:
    """Get or create the global breaking news detector."""
    global _global_detector
    if _global_detector is None:
        _global_detector = BreakingNewsDetector()
    return _global_detector


def detect_breaking_news(
    title: str,
    content: str = "",
    source_url: str = "",
    topic_key: Optional[str] = None,
) -> BreakingNewsResult:
    """
    Detect breaking news using the global detector.

    This maintains volume tracking across calls for spike detection.

    Args:
        title: Article title
        content: Article content
        source_url: Source URL
        topic_key: Topic key for volume tracking

    Returns:
        BreakingNewsResult with detection details
    """
    detector = get_global_detector()
    return detector.detect(
        title=title,
        content=content,
        source_url=source_url,
        topic_key=topic_key,
    )
