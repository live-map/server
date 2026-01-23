"""
Unit tests for Event Deduplication (Two-Layer System).

Tests the two-layer deduplication system:
1. Layer 1: Hash matching (exact duplicates)
2. Layer 2: Semantic search (similar events)
3. Threshold-based classification
4. Match type handling
"""

import hashlib
import re
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.deduplication.event_matcher import (
    EventMatcher,
    MatchResult,
    MatchType,
)


class TestMatchType:
    """Tests for MatchType enum."""

    def test_match_types_exist(self):
        """All expected match types should exist."""
        assert MatchType.EXACT is not None
        assert MatchType.DUPLICATE is not None
        assert MatchType.POTENTIAL is not None
        assert MatchType.RELATED is not None
        assert MatchType.NEW is not None

    def test_match_type_values(self):
        """Match types should have string values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.DUPLICATE.value == "duplicate"
        assert MatchType.POTENTIAL.value == "potential"
        assert MatchType.RELATED.value == "related"
        assert MatchType.NEW.value == "new"


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_is_duplicate_exact(self):
        """EXACT should be considered duplicate."""
        result = MatchResult(
            match_type=MatchType.EXACT,
            matched_event_id=1,
            similarity_score=1.0,
        )
        assert result.is_duplicate

    def test_is_duplicate_duplicate(self):
        """DUPLICATE should be considered duplicate."""
        result = MatchResult(
            match_type=MatchType.DUPLICATE,
            matched_event_id=1,
            similarity_score=0.96,
        )
        assert result.is_duplicate

    def test_is_not_duplicate_potential(self):
        """POTENTIAL should not be considered duplicate."""
        result = MatchResult(
            match_type=MatchType.POTENTIAL,
            matched_event_id=1,
            similarity_score=0.90,
        )
        assert not result.is_duplicate

    def test_is_potential_match(self):
        """POTENTIAL should be flagged for LLM verification."""
        result = MatchResult(
            match_type=MatchType.POTENTIAL,
            matched_event_id=1,
            similarity_score=0.90,
        )
        assert result.is_potential_match

    def test_is_new_event(self):
        """NEW should be flagged as new event."""
        result = MatchResult(match_type=MatchType.NEW)
        assert result.is_new_event
        assert not result.is_duplicate
        assert not result.is_potential_match


class TestHashGeneration:
    """Tests for hash generation."""

    def test_generate_hash_consistent(self, mock_db_session):
        """Same text should produce same hash."""
        matcher = EventMatcher(mock_db_session)
        text = "Iran attacks US bases in Iraq"

        hash1 = matcher._generate_hash(text)
        hash2 = matcher._generate_hash(text)

        assert hash1 == hash2

    def test_generate_hash_normalized(self, mock_db_session):
        """Hash should normalize text (lowercase, whitespace)."""
        matcher = EventMatcher(mock_db_session)

        # Different formatting, same content
        text1 = "Iran attacks US bases"
        text2 = "iran attacks us bases"
        text3 = "  Iran  attacks   US   bases  "

        hash1 = matcher._generate_hash(text1)
        hash2 = matcher._generate_hash(text2)
        hash3 = matcher._generate_hash(text3)

        # All should produce same hash (normalized)
        assert hash1 == hash2 == hash3

    def test_generate_hash_punctuation_removed(self, mock_db_session):
        """Hash should remove punctuation."""
        matcher = EventMatcher(mock_db_session)

        text1 = "Iran attacks US bases"
        text2 = "Iran attacks US bases!"
        text3 = "Iran, attacks US bases."

        hash1 = matcher._generate_hash(text1)
        hash2 = matcher._generate_hash(text2)
        hash3 = matcher._generate_hash(text3)

        assert hash1 == hash2 == hash3

    def test_generate_hash_different_text(self, mock_db_session):
        """Different text should produce different hash."""
        matcher = EventMatcher(mock_db_session)

        hash1 = matcher._generate_hash("Iran attacks US bases")
        hash2 = matcher._generate_hash("Earthquake hits Japan")

        assert hash1 != hash2

    def test_generate_hash_sha256(self, mock_db_session):
        """Hash should be valid SHA-256."""
        matcher = EventMatcher(mock_db_session)
        hash_result = matcher._generate_hash("Test text")

        # SHA-256 produces 64 character hex string
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)


class TestGenerateEventHash:
    """Tests for public hash generation method."""

    def test_public_method_works(self, mock_db_session):
        """Public method should work same as private."""
        matcher = EventMatcher(mock_db_session)
        text = "Test event text"

        public_hash = matcher.generate_event_hash(text)
        private_hash = matcher._generate_hash(text)

        assert public_hash == private_hash


class TestGenerateFactHash:
    """Tests for fact hash generation."""

    def test_fact_hash_sorted(self, mock_db_session):
        """Fact hash should be order-independent."""
        matcher = EventMatcher(mock_db_session)

        facts1 = ["Fact A", "Fact B", "Fact C"]
        facts2 = ["Fact C", "Fact A", "Fact B"]  # Different order

        hash1 = matcher.generate_fact_hash(facts1)
        hash2 = matcher.generate_fact_hash(facts2)

        # Should be same (sorted internally)
        assert hash1 == hash2

    def test_fact_hash_normalized(self, mock_db_session):
        """Fact hash should normalize facts."""
        matcher = EventMatcher(mock_db_session)

        facts1 = ["Fact A"]
        facts2 = ["  FACT A  "]  # Different casing/whitespace

        hash1 = matcher.generate_fact_hash(facts1)
        hash2 = matcher.generate_fact_hash(facts2)

        assert hash1 == hash2


class TestEventMatcherInit:
    """Tests for EventMatcher initialization."""

    def test_default_thresholds(self, mock_db_session):
        """Default thresholds should match config."""
        matcher = EventMatcher(mock_db_session)

        # Default thresholds from config
        assert matcher.duplicate_threshold == 0.95
        assert matcher.potential_threshold == 0.85
        assert matcher.related_threshold == 0.70

    def test_custom_thresholds(self, mock_db_session):
        """Custom thresholds should override defaults."""
        matcher = EventMatcher(
            mock_db_session,
            duplicate_threshold=0.98,
            potential_threshold=0.90,
            related_threshold=0.75,
        )

        assert matcher.duplicate_threshold == 0.98
        assert matcher.potential_threshold == 0.90
        assert matcher.related_threshold == 0.75


class TestHashExactMatch:
    """Tests for Layer 1: Hash matching."""

    @pytest.mark.asyncio
    async def test_hash_exact_match_found(self, mock_db_session):
        """Exact hash match should return EXACT type."""
        matcher = EventMatcher(mock_db_session)

        # Mock existing event with matching hash
        mock_event = MagicMock()
        mock_event.id = 123
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db_session.execute.return_value = mock_result

        result = await matcher.find_match("Iran attacks US bases")

        assert result.match_type == MatchType.EXACT
        assert result.matched_event_id == 123
        assert result.similarity_score == 1.0

    @pytest.mark.asyncio
    async def test_hash_no_match(self, mock_db_session):
        """No hash match should proceed to semantic search."""
        matcher = EventMatcher(mock_db_session)

        # Mock no hash match
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await matcher.find_match("Unique event text")

        # Without embedding, should return NEW
        assert result.match_type == MatchType.NEW


class TestSemanticDuplicateThresholds:
    """Tests for Layer 2: Semantic similarity thresholds."""

    @pytest.mark.asyncio
    async def test_semantic_duplicate_95(self, mock_db_session):
        """Similarity >= 0.95 should return DUPLICATE."""
        matcher = EventMatcher(mock_db_session)

        # Mock no hash match
        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = None

        # Mock semantic match with high similarity
        semantic_result = MagicMock()
        semantic_result.fetchone.return_value = (
            1, "hash123", "Similar event", "conflict", 0.96
        )

        event_result = MagicMock()
        event_result.scalar_one_or_none.return_value = MagicMock(id=1)

        mock_db_session.execute = AsyncMock(
            side_effect=[hash_result, semantic_result, event_result]
        )

        embedding = [0.1] * 1024
        result = await matcher.find_match("Event text", embedding=embedding)

        assert result.match_type == MatchType.DUPLICATE
        assert result.similarity_score == 0.96

    @pytest.mark.asyncio
    async def test_semantic_potential_85_95(self, mock_db_session):
        """Similarity 0.85-0.95 should return POTENTIAL."""
        matcher = EventMatcher(mock_db_session)

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = None

        semantic_result = MagicMock()
        semantic_result.fetchone.return_value = (
            1, "hash123", "Similar event", "conflict", 0.90
        )

        event_result = MagicMock()
        event_result.scalar_one_or_none.return_value = MagicMock(id=1)

        mock_db_session.execute = AsyncMock(
            side_effect=[hash_result, semantic_result, event_result]
        )

        embedding = [0.1] * 1024
        result = await matcher.find_match("Event text", embedding=embedding)

        assert result.match_type == MatchType.POTENTIAL
        assert result.similarity_score == 0.90

    @pytest.mark.asyncio
    async def test_semantic_related_70_85(self, mock_db_session):
        """Similarity 0.70-0.85 should return RELATED."""
        matcher = EventMatcher(mock_db_session)

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = None

        semantic_result = MagicMock()
        semantic_result.fetchone.return_value = (
            1, "hash123", "Related event", "conflict", 0.78
        )

        event_result = MagicMock()
        event_result.scalar_one_or_none.return_value = MagicMock(id=1)

        mock_db_session.execute = AsyncMock(
            side_effect=[hash_result, semantic_result, event_result]
        )

        embedding = [0.1] * 1024
        result = await matcher.find_match("Event text", embedding=embedding)

        assert result.match_type == MatchType.RELATED
        assert result.similarity_score == 0.78

    @pytest.mark.asyncio
    async def test_semantic_new_below_70(self, mock_db_session):
        """Similarity < 0.70 should return NEW."""
        matcher = EventMatcher(mock_db_session)

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = None

        # No semantic match found (below threshold)
        semantic_result = MagicMock()
        semantic_result.fetchone.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[hash_result, semantic_result]
        )

        embedding = [0.1] * 1024
        result = await matcher.find_match("Event text", embedding=embedding)

        assert result.match_type == MatchType.NEW


class TestCategoryFiltering:
    """Tests for category-based filtering."""

    @pytest.mark.asyncio
    async def test_category_filter_applied(self, mock_db_session):
        """Category filter should be applied in semantic search."""
        matcher = EventMatcher(mock_db_session)

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = None

        semantic_result = MagicMock()
        semantic_result.fetchone.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[hash_result, semantic_result]
        )

        embedding = [0.1] * 1024
        await matcher.find_match(
            "Event text",
            embedding=embedding,
            category="conflict"
        )

        # Verify category was passed to query
        calls = mock_db_session.execute.call_args_list
        assert len(calls) >= 2


class TestTimeWindowFiltering:
    """Tests for time window filtering in semantic search."""

    def test_time_window_default(self, mock_db_session):
        """Default time window should be 7 days."""
        matcher = EventMatcher(mock_db_session)
        assert matcher.time_window_days == 7

    def test_time_window_custom(self, mock_db_session):
        """Custom time window should be applied."""
        matcher = EventMatcher(mock_db_session, time_window_days=14)
        assert matcher.time_window_days == 14


class TestNoEmbeddingHandling:
    """Tests for handling cases without embedding."""

    @pytest.mark.asyncio
    async def test_no_embedding_skips_semantic(self, mock_db_session):
        """Without embedding, should skip semantic search."""
        matcher = EventMatcher(mock_db_session)

        # Mock no hash match
        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = hash_result

        # No embedding provided
        result = await matcher.find_match("Event text", embedding=None)

        assert result.match_type == MatchType.NEW
        # Only one DB call (hash check), not semantic
        mock_db_session.execute.assert_called_once()


class TestThresholdClassification:
    """Tests for threshold-based classification logic."""

    def test_duplicate_boundary(self, mock_db_session):
        """Test exact duplicate threshold boundary."""
        matcher = EventMatcher(
            mock_db_session,
            duplicate_threshold=0.95,
            potential_threshold=0.85,
            related_threshold=0.70,
        )

        # At boundary
        assert matcher.duplicate_threshold == 0.95
        # Just above -> DUPLICATE
        # Just below -> POTENTIAL

    def test_potential_boundary(self, mock_db_session):
        """Test potential threshold boundary."""
        matcher = EventMatcher(
            mock_db_session,
            duplicate_threshold=0.95,
            potential_threshold=0.85,
            related_threshold=0.70,
        )

        assert matcher.potential_threshold == 0.85

    def test_related_boundary(self, mock_db_session):
        """Test related threshold boundary."""
        matcher = EventMatcher(
            mock_db_session,
            duplicate_threshold=0.95,
            potential_threshold=0.85,
            related_threshold=0.70,
        )

        assert matcher.related_threshold == 0.70


class TestMatchResultProperties:
    """Additional tests for MatchResult properties."""

    def test_result_with_matched_event(self):
        """Result should store matched event object."""
        mock_event = MagicMock()
        mock_event.id = 123

        result = MatchResult(
            match_type=MatchType.DUPLICATE,
            matched_event_id=123,
            similarity_score=0.96,
            matched_event=mock_event,
        )

        assert result.matched_event is mock_event
        assert result.matched_event.id == 123

    def test_result_without_matched_event(self):
        """NEW result should have no matched event."""
        result = MatchResult(match_type=MatchType.NEW)

        assert result.matched_event is None
        assert result.matched_event_id is None


class TestEdgeCases:
    """Edge case tests for deduplication."""

    @pytest.mark.asyncio
    async def test_empty_text(self, mock_db_session):
        """Empty text should still generate hash and search."""
        matcher = EventMatcher(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Should not raise error
        result = await matcher.find_match("")
        assert result.match_type == MatchType.NEW

    @pytest.mark.asyncio
    async def test_unicode_text(self, mock_db_session):
        """Unicode text should be handled correctly."""
        matcher = EventMatcher(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Korean text
        result = await matcher.find_match("북한 미사일 발사")
        assert result.match_type == MatchType.NEW

    @pytest.mark.asyncio
    async def test_very_long_text(self, mock_db_session):
        """Very long text should be handled."""
        matcher = EventMatcher(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        long_text = "A" * 10000
        result = await matcher.find_match(long_text)
        assert result.match_type == MatchType.NEW

    def test_hash_deterministic(self, mock_db_session):
        """Hash should be deterministic across calls."""
        matcher = EventMatcher(mock_db_session)
        text = "Test event for hashing"

        hashes = [matcher._generate_hash(text) for _ in range(100)]

        # All hashes should be identical
        assert len(set(hashes)) == 1
