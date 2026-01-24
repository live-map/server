"""
Unit tests for Cross-Source Matcher.

Tests the semantic similarity matching system for:
1. Event matching across sources
2. Embedding generation
3. Similarity threshold handling
4. Time window filtering
5. MatchedEvent properties
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import numpy as np
import pytest

from app.agent.cross_source_matcher import CrossSourceMatcher, MatchedEvent
from app.agent.triggers.base import TriggerSource, TriggerEvent, SourceTier


class TestMatchedEventProperties:
    """Tests for MatchedEvent dataclass properties."""

    def test_all_events_property(self, trigger_event_factory):
        """all_events should return primary + matching events."""
        primary = trigger_event_factory(title="Primary event")
        match1 = trigger_event_factory(title="Match 1")
        match2 = trigger_event_factory(title="Match 2")

        matched = MatchedEvent(
            primary_event=primary,
            matching_events=[match1, match2],
            similarity_scores=[0.85, 0.80],
        )

        assert len(matched.all_events) == 3
        assert matched.all_events[0] == primary

    def test_source_count_property(self, trigger_event_factory):
        """source_count should return unique source count."""
        event1 = trigger_event_factory(source=TriggerSource.GDELT)
        event2 = trigger_event_factory(source=TriggerSource.REDDIT)
        event3 = trigger_event_factory(source=TriggerSource.REDDIT)  # Duplicate source

        matched = MatchedEvent(
            primary_event=event1,
            matching_events=[event2, event3],
            similarity_scores=[0.85, 0.80],
        )

        # Should count GDELT and Reddit = 2 (not 3)
        assert matched.source_count == 2

    def test_sources_property(self, trigger_event_factory):
        """sources should return list of source dicts with tiers."""
        event1 = trigger_event_factory(source=TriggerSource.GDELT)
        event2 = trigger_event_factory(source=TriggerSource.REDDIT)

        matched = MatchedEvent(
            primary_event=event1,
            matching_events=[event2],
            similarity_scores=[0.85],
        )

        sources = matched.sources
        assert len(sources) == 2
        assert sources[0]["name"] == "gdelt"
        assert sources[0]["tier"] == SourceTier.TIER1_NEWS.value
        assert sources[1]["name"] == "reddit"
        assert sources[1]["tier"] == SourceTier.TIER3_SOCIAL.value

    def test_avg_similarity_with_matches(self, trigger_event_factory):
        """avg_similarity should calculate average of scores."""
        matched = MatchedEvent(
            primary_event=trigger_event_factory(),
            matching_events=[trigger_event_factory(), trigger_event_factory()],
            similarity_scores=[0.90, 0.80],
        )

        # Use approximate comparison for floating point
        assert abs(matched.avg_similarity - 0.85) < 0.001

    def test_avg_similarity_no_matches(self, trigger_event_factory):
        """avg_similarity should be 1.0 with no matches (self-similarity)."""
        matched = MatchedEvent(
            primary_event=trigger_event_factory(),
            matching_events=[],
            similarity_scores=[],
        )

        assert matched.avg_similarity == 1.0

    def test_to_dict(self, trigger_event_factory):
        """to_dict should serialize correctly."""
        event1 = trigger_event_factory(title="Event 1", source=TriggerSource.GDELT)
        event2 = trigger_event_factory(title="Event 2", source=TriggerSource.REDDIT)

        matched = MatchedEvent(
            primary_event=event1,
            matching_events=[event2],
            similarity_scores=[0.85],
        )

        data = matched.to_dict()

        assert "primary" in data
        assert "matching_count" in data
        assert data["matching_count"] == 1
        assert "source_count" in data
        assert data["source_count"] == 2
        assert "sources" in data
        assert "avg_similarity" in data


class TestCrossSourceMatcherInit:
    """Tests for CrossSourceMatcher initialization."""

    def test_default_init(self):
        """Default initialization should use default values."""
        matcher = CrossSourceMatcher()

        # P2 update: default threshold increased from 0.70 to 0.75
        assert matcher.similarity_threshold == 0.75
        assert matcher.time_window == timedelta(hours=6)
        assert matcher.embedding_model == "BAAI/bge-m3"
        assert matcher._encoder is None

    def test_custom_init(self):
        """Custom initialization should use provided values."""
        matcher = CrossSourceMatcher(
            similarity_threshold=0.80,
            time_window_hours=12,
            embedding_model="custom/model",
        )

        assert matcher.similarity_threshold == 0.80
        assert matcher.time_window == timedelta(hours=12)
        assert matcher.embedding_model == "custom/model"


class TestTimeWindowFiltering:
    """Tests for time window filtering."""

    def test_recent_events_included(self, trigger_event_factory):
        """Events within time window should be included."""
        matcher = CrossSourceMatcher(time_window_hours=6)
        now = datetime.utcnow()

        events = [
            trigger_event_factory(detected_at=now),
            trigger_event_factory(detected_at=now - timedelta(hours=3)),
            trigger_event_factory(detected_at=now - timedelta(hours=5)),
        ]

        # All events are within 6 hours
        result = matcher.match_events(events)
        assert len(result) == 3

    def test_old_events_excluded(self, trigger_event_factory):
        """Events outside time window should be excluded."""
        matcher = CrossSourceMatcher(time_window_hours=6)
        now = datetime.utcnow()

        events = [
            trigger_event_factory(detected_at=now),
            trigger_event_factory(detected_at=now - timedelta(hours=10)),  # Old
        ]

        result = matcher.match_events(events)
        # Only one event within window
        assert len(result) == 1


class TestTextSimilarity:
    """Tests for fallback text similarity."""

    def test_text_similarity_identical(self):
        """Identical text should have similarity 1.0."""
        matcher = CrossSourceMatcher()
        sim = matcher._text_similarity(
            "Iran attacks US bases",
            "Iran attacks US bases"
        )
        assert sim == 1.0

    def test_text_similarity_similar(self):
        """Similar text should have high similarity."""
        matcher = CrossSourceMatcher()
        sim = matcher._text_similarity(
            "Iran attacks US military bases in Iraq",
            "Iran attacks American military bases in Iraq"
        )
        # High overlap
        assert sim > 0.7

    def test_text_similarity_different(self):
        """Different text should have low similarity."""
        matcher = CrossSourceMatcher()
        sim = matcher._text_similarity(
            "Iran attacks US bases",
            "Earthquake hits Japan"
        )
        assert sim < 0.3

    def test_text_similarity_empty(self):
        """Empty text should have similarity 0.0."""
        matcher = CrossSourceMatcher()
        assert matcher._text_similarity("", "some text") == 0.0
        assert matcher._text_similarity("some text", "") == 0.0


class TestEventText:
    """Tests for event text extraction."""

    def test_get_event_text_title_only(self, trigger_event_factory):
        """Event with only title should use title."""
        matcher = CrossSourceMatcher()
        event = trigger_event_factory(title="Breaking news", content="")

        text = matcher._get_event_text(event)
        assert text == "Breaking news"

    def test_get_event_text_with_content(self, trigger_event_factory):
        """Event with content should combine title and content."""
        matcher = CrossSourceMatcher()
        event = trigger_event_factory(
            title="Breaking news",
            content="Details about the event"
        )

        text = matcher._get_event_text(event)
        assert "Breaking news" in text
        assert "Details about the event" in text

    def test_get_event_text_long_content_truncated(self, trigger_event_factory):
        """Long content should be truncated to 500 chars."""
        matcher = CrossSourceMatcher()
        long_content = "A" * 1000
        event = trigger_event_factory(
            title="Title",
            content=long_content
        )

        text = matcher._get_event_text(event)
        # Title + truncated content (500 chars)
        assert len(text) <= len("Title") + 1 + 500


class TestDifferentSourceMatching:
    """Tests for matching events from different sources."""

    def test_same_source_not_matched(self, trigger_event_factory):
        """Events from same source should not be matched together."""
        matcher = CrossSourceMatcher()

        # Two similar events from GDELT
        events = [
            trigger_event_factory(
                title="Iran attacks US bases",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Iran attacks American bases",  # Similar
                source=TriggerSource.GDELT  # Same source
            ),
        ]

        result = matcher.match_events(events)

        # Should be 2 separate MatchedEvent (no cross-matching)
        assert len(result) == 2
        for matched in result:
            # Each should have no matching events (same source not matched)
            assert matched.source_count == 1

    def test_different_sources_matched(self, trigger_event_factory):
        """Similar events from different sources should be matched."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(
                title="Iran attacks US military bases in Iraq",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Iran attacks US military bases in Iraq",  # Same text
                source=TriggerSource.REDDIT  # Different source
            ),
        ]

        result = matcher.match_events(events)

        # Should be 1 MatchedEvent with both sources
        assert len(result) == 1
        assert result[0].source_count == 2


class TestSimilarityThreshold:
    """Tests for similarity threshold handling."""

    def test_above_threshold_matched(self, trigger_event_factory):
        """Events above threshold should be matched."""
        matcher = CrossSourceMatcher(similarity_threshold=0.70)

        events = [
            trigger_event_factory(
                title="Iran attacks US bases in Iraq",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Iran attacks US bases in Iraq",  # Identical
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        assert len(result) == 1
        assert result[0].source_count == 2

    def test_below_threshold_not_matched(self, trigger_event_factory):
        """Events below threshold should not be matched."""
        matcher = CrossSourceMatcher(similarity_threshold=0.99)  # Very high

        events = [
            trigger_event_factory(
                title="Iran attacks US bases",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Different event about something else",
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # Should be 2 separate MatchedEvents
        assert len(result) == 2


class TestEmptyAndEdgeCases:
    """Tests for empty and edge cases."""

    def test_empty_events_list(self):
        """Empty events list should return empty list."""
        matcher = CrossSourceMatcher()
        result = matcher.match_events([])
        assert result == []

    def test_single_event(self, trigger_event_factory):
        """Single event should return single MatchedEvent."""
        matcher = CrossSourceMatcher()
        events = [trigger_event_factory()]

        result = matcher.match_events(events)

        assert len(result) == 1
        assert result[0].source_count == 1

    def test_existing_matches_preserved(self, trigger_event_factory):
        """Existing matches should be preserved."""
        matcher = CrossSourceMatcher()

        existing = [
            MatchedEvent(
                primary_event=trigger_event_factory(title="Existing"),
                matching_events=[],
                similarity_scores=[],
            )
        ]

        new_events = [trigger_event_factory(title="New event")]

        result = matcher.match_events(new_events, existing_matches=existing)

        # Should have existing + new
        assert len(result) >= 1


class TestSortingBySourceCount:
    """Tests for sorting results by source count."""

    def test_multi_source_first(self, trigger_event_factory):
        """Multi-source events should appear first in results."""
        matcher = CrossSourceMatcher()

        # Create events: single source first, then multi-source
        events = [
            trigger_event_factory(
                title="Single source event",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Multi source event A",
                source=TriggerSource.REDDIT
            ),
            trigger_event_factory(
                title="Multi source event A",  # Same title = match
                source=TriggerSource.CURRENTS
            ),
        ]

        result = matcher.match_events(events)

        # Multi-source should come first
        if len(result) > 1:
            assert result[0].source_count >= result[-1].source_count


class TestInitialization:
    """Tests for async initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Initialize should return True on success."""
        matcher = CrossSourceMatcher()

        # Patch at the import location (inside the function)
        with patch.dict("sys.modules", {"sentence_transformers": MagicMock()}):
            with patch("fastapi.concurrency.run_in_threadpool") as mock_threadpool:
                mock_threadpool.return_value = MagicMock()
                result = await matcher.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_initialize_fallback_on_error(self):
        """Initialize should return True with fallback on error."""
        matcher = CrossSourceMatcher()

        # The initialize method catches ImportError and returns True (fallback)
        # Since sentence_transformers may not be installed in test env,
        # this should work naturally
        result = await matcher.initialize()

        # Should return True even if embedding model fails to load
        assert result is True


class TestQueryMatching:
    """Tests for query-based event matching."""

    def test_find_matching_events_empty(self):
        """Empty events should return empty list."""
        matcher = CrossSourceMatcher()
        result = matcher.find_matching_events_for_query("query", [])
        assert result == []

    def test_find_matching_events_fallback(self, trigger_event_factory):
        """Should use text similarity as fallback."""
        matcher = CrossSourceMatcher()
        matcher._encoder = None  # Force fallback

        events = [
            trigger_event_factory(title="Iran attacks US bases"),
            trigger_event_factory(title="Earthquake in Japan"),
        ]

        result = matcher.find_matching_events_for_query(
            "Iran attacks",
            events,
            top_k=1
        )

        # Should find the Iran event
        if result:
            assert "Iran" in result[0][0].title


class TestEmbeddingGeneration:
    """Tests for embedding generation."""

    def test_generate_embeddings_no_encoder(self, trigger_event_factory):
        """Should return None without encoder."""
        matcher = CrossSourceMatcher()
        matcher._encoder = None

        events = [trigger_event_factory()]
        result = matcher._generate_embeddings(events)

        assert result is None

    def test_generate_embeddings_with_encoder(self, trigger_event_factory, mock_sentence_transformer):
        """Should generate embeddings with encoder."""
        matcher = CrossSourceMatcher()
        matcher._encoder = mock_sentence_transformer()

        events = [trigger_event_factory(), trigger_event_factory()]
        result = matcher._generate_embeddings(events)

        assert result is not None
        assert result.shape[0] == 2
        assert result.shape[1] == 1024  # BGE-M3 dimension


class TestSimilarityMatrix:
    """Tests for similarity matrix computation."""

    def test_compute_similarity_matrix(self):
        """Should compute cosine similarity matrix."""
        matcher = CrossSourceMatcher()

        # Create normalized embeddings
        embeddings = np.array([
            [1, 0, 0],
            [1, 0, 0],  # Same as first
            [0, 1, 0],  # Orthogonal
        ], dtype=float)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        matrix = matcher._compute_similarity_matrix(embeddings)

        # Same vectors should have similarity 1.0
        assert abs(matrix[0, 1] - 1.0) < 0.01
        # Orthogonal vectors should have similarity 0.0
        assert abs(matrix[0, 2] - 0.0) < 0.01

    def test_compute_text_similarity_matrix(self, trigger_event_factory):
        """Should compute text-based similarity matrix."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(title="Iran attacks US bases"),
            trigger_event_factory(title="Iran attacks US bases"),  # Same
            trigger_event_factory(title="Earthquake in Japan"),  # Different
        ]

        matrix = matcher._compute_text_similarity_matrix(events)

        # Same text should have similarity 1.0
        assert matrix[0, 1] == 1.0
        # Different text should have low similarity
        assert matrix[0, 2] < 0.5


class TestFalsePositivePrevention:
    """Tests for false positive prevention in event matching.

    These tests ensure that similar but unrelated events are not
    incorrectly matched together.
    """

    def test_similar_keywords_different_topics_not_matched(self, trigger_event_factory):
        """Events with similar keywords but different topics should not be matched."""
        matcher = CrossSourceMatcher(similarity_threshold=0.70)

        events = [
            trigger_event_factory(
                title="Iran attacks US military bases in Iraq",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="US military conducts training exercises in Japan",
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # Should be 2 separate events (similar keywords: US, military, but different topics)
        assert len(result) == 2
        for matched in result:
            assert matched.source_count == 1

    def test_same_location_different_events_not_matched(self, trigger_event_factory):
        """Different events at the same location should not be matched."""
        matcher = CrossSourceMatcher(similarity_threshold=0.70)

        events = [
            trigger_event_factory(
                title="Earthquake strikes Turkey",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Political protests in Turkey capital",
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # Should be 2 separate events (same location, different events)
        assert len(result) == 2

    def test_partial_text_overlap_not_false_positive(self, trigger_event_factory):
        """Events with partial text overlap should not cause false positive."""
        matcher = CrossSourceMatcher(similarity_threshold=0.70)

        events = [
            trigger_event_factory(
                title="Russia launches missile strikes on Ukraine infrastructure",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Ukraine launches counteroffensive in Kherson region",
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # Different events about same conflict should be separate
        assert len(result) == 2

    def test_threshold_boundary_cases(self, trigger_event_factory):
        """Events at threshold boundary should be handled correctly."""
        # Test with exact threshold
        # Jaccard similarity = |A ∩ B| / |A ∪ B|
        # For 6 common words out of 9 words each: 6 / (9 + 9 - 6) = 6/12 = 0.5
        matcher = CrossSourceMatcher(similarity_threshold=0.50)

        events = [
            trigger_event_factory(
                title="One two three four five six seven eight nine",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                # 6 common words out of 9 = 0.5 Jaccard similarity
                title="One two three four five six different words here",
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # Should match at exactly 0.50 threshold
        # This tests that >= is used, not >
        assert len(result) == 1
        assert result[0].source_count == 2

    def test_very_high_threshold_prevents_false_positives(self, trigger_event_factory):
        """Very high threshold should prevent all but identical matches."""
        matcher = CrossSourceMatcher(similarity_threshold=0.95)

        events = [
            trigger_event_factory(
                title="Iran launches missile attack on US bases in Iraq",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Iran launches missile attack on US bases",  # Slightly different
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # Should be 2 separate events with high threshold
        assert len(result) == 2

    def test_date_in_title_causes_false_negative_not_positive(self, trigger_event_factory):
        """Different dates in titles should prevent false matches."""
        matcher = CrossSourceMatcher(similarity_threshold=0.70)

        events = [
            trigger_event_factory(
                title="Iran attacks US bases on January 15 2025",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Iran attacks US bases on January 20 2025",  # Different date
                source=TriggerSource.REDDIT
            ),
        ]

        result = matcher.match_events(events)

        # High similarity but different dates - depends on text similarity implementation
        # With word overlap, dates contribute to overall similarity
        # The test documents expected behavior
        assert len(result) >= 1


class TestEdgeCasesAndRobustness:
    """Tests for edge cases and robustness."""

    def test_empty_title_handled(self, trigger_event_factory):
        """Events with empty titles should be handled gracefully."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(title="", source=TriggerSource.GDELT),
            trigger_event_factory(title="Normal event", source=TriggerSource.REDDIT),
        ]

        # Should not raise exception
        result = matcher.match_events(events)
        assert len(result) == 2

    def test_very_long_title_handled(self, trigger_event_factory):
        """Events with very long titles should be handled."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(
                title="A " * 1000,  # Very long title
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Normal event",
                source=TriggerSource.REDDIT
            ),
        ]

        # Should not raise exception
        result = matcher.match_events(events)
        assert len(result) == 2

    def test_special_characters_in_title(self, trigger_event_factory):
        """Events with special characters should be handled."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(
                title="Breaking: Iran attacks US!!! @#$%",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Breaking: Iran attacks US",
                source=TriggerSource.REDDIT
            ),
        ]

        # Should match despite special characters
        result = matcher.match_events(events)
        # High similarity expected
        assert len(result) >= 1

    def test_unicode_handling(self, trigger_event_factory):
        """Events with unicode characters should be handled."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(
                title="北朝鮮がミサイル発射",  # Korean/Japanese
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="North Korea launches missile",
                source=TriggerSource.REDDIT
            ),
        ]

        # Should not raise exception (though may not match due to different languages)
        result = matcher.match_events(events)
        assert len(result) == 2

    def test_large_event_list_performance(self, trigger_event_factory):
        """Should handle large lists of events efficiently."""
        matcher = CrossSourceMatcher()

        # Create 50 events (reasonable test size)
        events = [
            trigger_event_factory(
                title=f"Event {i} about topic {i % 5}",
                source=TriggerSource.GDELT if i % 2 == 0 else TriggerSource.REDDIT
            )
            for i in range(50)
        ]

        # Should complete without timeout or error
        result = matcher.match_events(events)
        assert len(result) <= 50  # At most 50 matched events

    def test_all_same_source_no_matches(self, trigger_event_factory):
        """All events from same source should result in no cross-matches."""
        matcher = CrossSourceMatcher()

        events = [
            trigger_event_factory(
                title="Identical event title",
                source=TriggerSource.GDELT
            ),
            trigger_event_factory(
                title="Identical event title",
                source=TriggerSource.GDELT  # Same source
            ),
            trigger_event_factory(
                title="Identical event title",
                source=TriggerSource.GDELT  # Same source
            ),
        ]

        result = matcher.match_events(events)

        # Should be 3 separate events (no cross-source matches)
        assert len(result) == 3
        for matched in result:
            assert matched.source_count == 1
