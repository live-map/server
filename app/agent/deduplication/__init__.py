"""
Deduplication module for news events.

Features:
1. Title matching (O(n)) - Fast string similarity using SequenceMatcher
2. Hash matching (O(1)) - Fast exact match
3. Semantic search (pgvector) - Similarity-based matching
4. Entity matching - Key entity overlap detection
5. DBSCAN clustering - Group related events into story clusters

Multi-Layer Deduplication Strategy:
- Layer 1: Title similarity (fast, no embedding needed)
- Layer 2: Hash + Semantic (embedding-based)
- Layer 3: Re-embedding with canonical title after LLM processing
"""

from .event_matcher import EventMatcher, MatchResult, MatchType
from .update_detector import UpdateDetector, UpdateType, UpdateCheckResult
from .event_clusterer import EventClusterer, ClusterInfo, cluster_and_update_events
from .title_matcher import TitleMatcher, TitleMatchResult, get_title_matcher

__all__ = [
    # Title Matching (Layer 1)
    "TitleMatcher",
    "TitleMatchResult",
    "get_title_matcher",
    # Event Matching (Layer 2)
    "EventMatcher",
    "MatchResult",
    "MatchType",
    # Update Detection
    "UpdateDetector",
    "UpdateType",
    "UpdateCheckResult",
    # Clustering
    "EventClusterer",
    "ClusterInfo",
    "cluster_and_update_events",
]
