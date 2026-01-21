"""
Event Matcher for two-layer deduplication.

Layer 1: Hash matching (O(1))
- Fast exact match using event_hash
- Uses normalized text for hash generation

Layer 2: Semantic search (pgvector)
- Cosine similarity using BGE-M3 embeddings
- Configurable thresholds for duplicate/related detection

Similarity thresholds:
- >= 0.95: Duplicate (skip)
- 0.85-0.94: Potential match (LLM verification needed)
- 0.70-0.84: Related event (link as story chain)
- < 0.70: Different event (create new)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.event import Event

logger = logging.getLogger(__name__)


class MatchType(str, Enum):
    """Type of event match."""

    EXACT = "exact"  # Hash match
    DUPLICATE = "duplicate"  # Semantic similarity >= 0.95
    POTENTIAL = "potential"  # 0.85 <= similarity < 0.95
    RELATED = "related"  # 0.70 <= similarity < 0.85
    NEW = "new"  # similarity < 0.70


@dataclass
class MatchResult:
    """Result of event matching."""

    match_type: MatchType
    matched_event_id: int | None = None
    similarity_score: float | None = None
    matched_event: "Event | None" = None

    @property
    def is_duplicate(self) -> bool:
        """Check if this is a duplicate that should be skipped."""
        return self.match_type in (MatchType.EXACT, MatchType.DUPLICATE)

    @property
    def is_potential_match(self) -> bool:
        """Check if this needs LLM verification."""
        return self.match_type == MatchType.POTENTIAL

    @property
    def is_new_event(self) -> bool:
        """Check if this is a new event."""
        return self.match_type == MatchType.NEW


class EventMatcher:
    """
    Two-layer event deduplication.

    Usage:
        matcher = EventMatcher(db_session)
        result = await matcher.find_match(event_text, embedding, category)

        if result.is_duplicate:
            print("Skipping duplicate event")
        elif result.is_potential_match:
            # Use LLM to verify
            ...
        else:
            # Create new event
            ...
    """

    def __init__(
        self,
        db: AsyncSession,
        duplicate_threshold: float = 0.95,
        potential_threshold: float = 0.85,
        related_threshold: float = 0.70,
        time_window_days: int = 7,
    ):
        """
        Initialize event matcher.

        Args:
            db: Database session
            duplicate_threshold: Similarity above this = duplicate
            potential_threshold: Similarity above this = potential match
            related_threshold: Similarity above this = related event
            time_window_days: Only check events within this time window
        """
        self.db = db
        self.duplicate_threshold = duplicate_threshold
        self.potential_threshold = potential_threshold
        self.related_threshold = related_threshold
        self.time_window_days = time_window_days

    async def find_match(
        self,
        event_text: str,
        embedding: list[float] | None = None,
        category: str | None = None,
    ) -> MatchResult:
        """
        Find matching event using two-layer approach.

        Args:
            event_text: Event description text
            embedding: Pre-computed embedding (optional)
            category: Event category for filtering (optional)

        Returns:
            MatchResult with match type and details
        """
        # Generate event hash
        event_hash = self._generate_hash(event_text)

        # Layer 1: Hash matching
        hash_match = await self._find_by_hash(event_hash)
        if hash_match:
            logger.info(f"Hash match found: event_id={hash_match.id}")
            return MatchResult(
                match_type=MatchType.EXACT,
                matched_event_id=hash_match.id,
                similarity_score=1.0,
                matched_event=hash_match,
            )

        # Layer 2: Semantic search (if embedding provided)
        if embedding:
            semantic_match = await self._find_by_similarity(
                embedding, category
            )
            if semantic_match:
                return semantic_match

        # No match found
        return MatchResult(match_type=MatchType.NEW)

    async def _find_by_hash(self, event_hash: str) -> "Event | None":
        """Find event by exact hash match."""
        from app.models.event import Event

        result = await self.db.execute(
            select(Event).where(
                Event.event_hash == event_hash,
                Event.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def _find_by_similarity(
        self,
        embedding: list[float],
        category: str | None = None,
    ) -> MatchResult | None:
        """
        Find event by semantic similarity using pgvector.

        Uses cosine distance for similarity calculation.
        """
        from app.models.event import Event

        # Time window filter
        cutoff_date = datetime.utcnow() - timedelta(days=self.time_window_days)

        # Build query with pgvector cosine distance
        # Cosine distance = 1 - cosine_similarity
        # So we need distance <= (1 - threshold)
        max_distance = 1 - self.related_threshold

        # Build embedding array literal for SQL
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Query using raw SQL for pgvector operations
        query = text(f"""
            SELECT
                id,
                event_hash,
                canonical_title,
                category,
                1 - (embedding <=> :embedding::vector) as similarity
            FROM events
            WHERE
                is_active = true
                AND created_at >= :cutoff_date
                AND embedding IS NOT NULL
                AND (embedding <=> :embedding::vector) <= :max_distance
                {"AND category = :category" if category else ""}
            ORDER BY embedding <=> :embedding::vector
            LIMIT 1
        """)

        params = {
            "embedding": embedding_str,
            "cutoff_date": cutoff_date,
            "max_distance": max_distance,
        }
        if category:
            params["category"] = category

        result = await self.db.execute(query, params)
        row = result.fetchone()

        if not row:
            return None

        event_id, event_hash, canonical_title, matched_category, similarity = row

        logger.info(
            f"Semantic match found: event_id={event_id}, "
            f"similarity={similarity:.3f}, title={canonical_title[:50]}"
        )

        # Determine match type based on similarity
        if similarity >= self.duplicate_threshold:
            match_type = MatchType.DUPLICATE
        elif similarity >= self.potential_threshold:
            match_type = MatchType.POTENTIAL
        else:
            match_type = MatchType.RELATED

        # Fetch full event object
        event_result = await self.db.execute(
            select(Event).where(Event.id == event_id)
        )
        matched_event = event_result.scalar_one_or_none()

        return MatchResult(
            match_type=match_type,
            matched_event_id=event_id,
            similarity_score=similarity,
            matched_event=matched_event,
        )

    def _generate_hash(self, text: str) -> str:
        """
        Generate deterministic hash from text.

        Normalizes text before hashing:
        - Lowercase
        - Remove extra whitespace
        - Remove punctuation
        - Sort words (order-independent)
        """
        # Normalize text
        normalized = text.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)

        # Sort words for order-independence (optional, can remove for strict matching)
        # words = sorted(normalized.split())
        # normalized = ' '.join(words)

        # Generate SHA-256 hash
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def generate_event_hash(self, text: str) -> str:
        """Public method to generate event hash."""
        return self._generate_hash(text)

    def generate_fact_hash(self, facts: list[str]) -> str:
        """
        Generate hash from list of facts for update detection.

        Facts are sorted and normalized before hashing.
        """
        # Normalize and sort facts
        normalized_facts = sorted([
            re.sub(r'\s+', ' ', f.lower().strip())
            for f in facts
        ])

        # Join and hash
        combined = '|'.join(normalized_facts)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()
