"""
Deduplication module for news events.

Features:
1. Hash matching (O(1)) - Fast exact match
2. Semantic search (pgvector) - Similarity-based matching
3. DBSCAN clustering - Group related events into story clusters
"""

from .event_matcher import EventMatcher, MatchResult, MatchType
from .update_detector import UpdateDetector, UpdateType, UpdateCheckResult
from .event_clusterer import EventClusterer, ClusterInfo, cluster_and_update_events

__all__ = [
    "EventMatcher",
    "MatchResult",
    "MatchType",
    "UpdateDetector",
    "UpdateType",
    "UpdateCheckResult",
    "EventClusterer",
    "ClusterInfo",
    "cluster_and_update_events",
]
