"""
Cross-Source Matcher

Matches events across different sources using semantic similarity.
Enables multi-source cross-verification for confidence scoring.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from .triggers.base import TriggerEvent, TriggerSource, SourceTier, SOURCE_TIER_MAP

logger = logging.getLogger(__name__)


@dataclass
class MatchedEvent:
    """Represents an event matched across multiple sources"""
    primary_event: TriggerEvent
    matching_events: list[TriggerEvent] = field(default_factory=list)
    similarity_scores: list[float] = field(default_factory=list)

    @property
    def all_events(self) -> list[TriggerEvent]:
        """Get all events including primary"""
        return [self.primary_event] + self.matching_events

    @property
    def source_count(self) -> int:
        """Count of unique sources"""
        sources = set(e.source for e in self.all_events)
        return len(sources)

    @property
    def sources(self) -> list[dict]:
        """Get list of sources with their tiers"""
        seen = set()
        sources = []
        for event in self.all_events:
            if event.source.value not in seen:
                seen.add(event.source.value)
                sources.append({
                    "name": event.source.value,
                    "tier": SOURCE_TIER_MAP.get(event.source, SourceTier.TIER2_NEWS).value,
                })
        return sources

    @property
    def avg_similarity(self) -> float:
        """Average similarity score of matches"""
        if not self.similarity_scores:
            return 1.0  # Primary event is 100% similar to itself
        return sum(self.similarity_scores) / len(self.similarity_scores)

    def to_dict(self) -> dict:
        return {
            "primary": self.primary_event.to_dict(),
            "matching_count": len(self.matching_events),
            "source_count": self.source_count,
            "sources": self.sources,
            "avg_similarity": self.avg_similarity,
        }


class CrossSourceMatcher:
    """
    Matches events across sources using semantic similarity.

    Uses embedding-based similarity for:
    1. Finding the same story across different sources
    2. Grouping related events for confidence scoring
    3. Detecting duplicate coverage

    P2 Enhancement: Increased default threshold from 0.70 to 0.75 to reduce
    false positives where different events are incorrectly grouped together.
    """

    # P2: Higher threshold for stricter duplicate detection
    DEFAULT_SIMILARITY_THRESHOLD = 0.75  # Was 0.70

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        time_window_hours: int = 6,
        embedding_model: str = "BAAI/bge-m3",
    ):
        self.similarity_threshold = similarity_threshold
        self.time_window = timedelta(hours=time_window_hours)
        self.embedding_model = embedding_model
        self._encoder = None

    async def initialize(self) -> bool:
        """Initialize the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            from fastapi.concurrency import run_in_threadpool

            # Load model in thread pool to not block
            self._encoder = await run_in_threadpool(
                SentenceTransformer,
                self.embedding_model
            )
            logger.info(f"Cross-source matcher initialized with {self.embedding_model}")
            return True
        except Exception as e:
            logger.warning(f"Could not load embedding model: {e}")
            logger.info("Using fallback text similarity")
            return True

    def generate_embedding_for_text(self, text: str) -> list[float] | None:
        """
        Generate embedding for a single text string.

        P0 Fix: This method enables semantic deduplication by providing
        embeddings for duplicate checking.

        Args:
            text: Text to generate embedding for

        Returns:
            Embedding as list of floats, or None if encoder unavailable
        """
        if not self._encoder:
            return None

        try:
            embedding = self._encoder.encode(
                [text],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}")
            return None

    def match_events(
        self,
        events: list[TriggerEvent],
        existing_matches: list[MatchedEvent] | None = None,
    ) -> list[MatchedEvent]:
        """
        Match events across sources.

        Groups events that are semantically similar and from different sources.

        Args:
            events: New events to match
            existing_matches: Previously matched events to extend

        Returns:
            List of matched event groups
        """
        if not events:
            return existing_matches or []

        # Filter by time window
        cutoff = datetime.utcnow() - self.time_window
        recent_events = [e for e in events if e.detected_at >= cutoff]

        if not recent_events:
            return existing_matches or []

        # Generate embeddings
        embeddings = self._generate_embeddings(recent_events)

        # Build similarity matrix
        if embeddings is not None:
            similarity_matrix = self._compute_similarity_matrix(embeddings)
        else:
            similarity_matrix = self._compute_text_similarity_matrix(recent_events)

        # Find matches
        matched_events = self._find_matches(
            recent_events,
            similarity_matrix,
            existing_matches,
        )

        return matched_events

    def _generate_embeddings(
        self, events: list[TriggerEvent]
    ) -> np.ndarray | None:
        """Generate embeddings for events"""
        if not self._encoder:
            return None

        try:
            texts = [self._get_event_text(e) for e in events]
            embeddings = self._encoder.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return np.array(embeddings)
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return None

    def _compute_similarity_matrix(
        self, embeddings: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity matrix"""
        # Embeddings are already normalized, so dot product = cosine similarity
        return np.dot(embeddings, embeddings.T)

    def _compute_text_similarity_matrix(
        self, events: list[TriggerEvent]
    ) -> np.ndarray:
        """Fallback: compute text-based similarity"""
        n = len(events)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i, n):
                sim = self._text_similarity(
                    self._get_event_text(events[i]),
                    self._get_event_text(events[j]),
                )
                matrix[i, j] = sim
                matrix[j, i] = sim

        return matrix

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _find_matches(
        self,
        events: list[TriggerEvent],
        similarity_matrix: np.ndarray,
        existing_matches: list[MatchedEvent] | None,
    ) -> list[MatchedEvent]:
        """Find matching events based on similarity"""
        n = len(events)
        matched_indices = set()
        result: list[MatchedEvent] = []

        # Start with existing matches
        if existing_matches:
            result = list(existing_matches)
            # TODO: Try to extend existing matches with new events

        # Find new matches
        for i in range(n):
            if i in matched_indices:
                continue

            # Find all events similar to this one
            similar_indices = []
            similar_scores = []

            for j in range(n):
                if i == j or j in matched_indices:
                    continue

                sim = similarity_matrix[i, j]
                if sim >= self.similarity_threshold:
                    # Only match if from different sources
                    if events[i].source != events[j].source:
                        similar_indices.append(j)
                        similar_scores.append(float(sim))

            # Create match if we found similar events from different sources
            if similar_indices:
                matched_event = MatchedEvent(
                    primary_event=events[i],
                    matching_events=[events[j] for j in similar_indices],
                    similarity_scores=similar_scores,
                )
                result.append(matched_event)

                # Mark all as matched
                matched_indices.add(i)
                matched_indices.update(similar_indices)
            else:
                # Single-source event
                matched_event = MatchedEvent(
                    primary_event=events[i],
                    matching_events=[],
                    similarity_scores=[],
                )
                result.append(matched_event)
                matched_indices.add(i)

        # Sort by source count (multi-source first)
        result.sort(key=lambda m: m.source_count, reverse=True)

        return result

    def _get_event_text(self, event: TriggerEvent) -> str:
        """Get text representation of event for embedding"""
        parts = [event.title]
        if event.content:
            parts.append(event.content[:500])
        return " ".join(parts)

    def is_duplicate_of_existing(
        self,
        new_event: TriggerEvent,
        existing_events: list[TriggerEvent],
        strict_threshold: float = 0.85,
    ) -> tuple[bool, TriggerEvent | None, float]:
        """
        P2 Enhancement: Check if a new event is a duplicate of existing events.

        Uses a stricter threshold (0.85) than regular matching to ensure
        we only flag true duplicates.

        Args:
            new_event: The new event to check
            existing_events: List of already published/processed events
            strict_threshold: Similarity threshold for duplicate detection (default 0.85)

        Returns:
            (is_duplicate, matched_event, similarity_score)
        """
        if not existing_events:
            return False, None, 0.0

        if not self._encoder:
            # Fallback to text similarity
            new_text = self._get_event_text(new_event)
            for event in existing_events:
                sim = self._text_similarity(new_text, self._get_event_text(event))
                if sim >= strict_threshold:
                    return True, event, sim
            return False, None, 0.0

        # Use embeddings
        new_emb = self._encoder.encode(
            [self._get_event_text(new_event)],
            normalize_embeddings=True,
        )[0]

        existing_embs = self._generate_embeddings(existing_events)
        if existing_embs is None:
            return False, None, 0.0

        similarities = np.dot(existing_embs, new_emb)
        max_idx = np.argmax(similarities)
        max_sim = float(similarities[max_idx])

        if max_sim >= strict_threshold:
            return True, existing_events[max_idx], max_sim

        return False, None, max_sim

    def find_matching_events_for_query(
        self,
        query: str,
        events: list[TriggerEvent],
        top_k: int = 5,
    ) -> list[tuple[TriggerEvent, float]]:
        """
        Find events matching a query string.

        Useful for cross-verification queries.

        Args:
            query: Search query
            events: Events to search
            top_k: Number of results

        Returns:
            List of (event, similarity_score) tuples
        """
        if not events:
            return []

        if self._encoder:
            # Use embeddings
            query_emb = self._encoder.encode(
                [query],
                normalize_embeddings=True,
            )[0]

            event_embs = self._generate_embeddings(events)
            if event_embs is not None:
                similarities = np.dot(event_embs, query_emb)
                top_indices = np.argsort(similarities)[-top_k:][::-1]

                return [
                    (events[i], float(similarities[i]))
                    for i in top_indices
                    if similarities[i] >= self.similarity_threshold
                ]

        # Fallback: text similarity
        results = []
        for event in events:
            sim = self._text_similarity(query, self._get_event_text(event))
            if sim >= self.similarity_threshold:
                results.append((event, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
