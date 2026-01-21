"""
Deduplication module for news events.

Two-layer deduplication:
1. Hash matching (O(1)) - Fast exact match
2. Semantic search (pgvector) - Similarity-based matching
"""

from .event_matcher import EventMatcher, MatchResult, MatchType
from .update_detector import UpdateDetector, UpdateType, UpdateCheckResult

__all__ = [
    "EventMatcher",
    "MatchResult",
    "MatchType",
    "UpdateDetector",
    "UpdateType",
    "UpdateCheckResult",
]
