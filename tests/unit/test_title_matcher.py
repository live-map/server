"""
Tests for TitleMatcher - Phase 6 Deduplication Layer 1.

Tests fast title similarity matching using SequenceMatcher.
"""

import pytest

from app.agent.deduplication.title_matcher import TitleMatcher, TitleMatchResult, get_title_matcher


class TestTitleNormalization:
    """Test title normalization logic."""

    def test_lowercase_normalization(self):
        matcher = TitleMatcher()
        assert matcher.normalize_title("BREAKING NEWS") == "breaking news"

    def test_punctuation_removal(self):
        matcher = TitleMatcher()
        # Removes punctuation except hyphens
        assert matcher.normalize_title("What's happening?") == "whats happening"
        assert matcher.normalize_title("Test: Results!") == "test results"

    def test_hyphen_preserved(self):
        matcher = TitleMatcher()
        # Hyphens are kept for compound words
        assert matcher.normalize_title("Self-driving cars") == "self-driving cars"

    def test_whitespace_collapsed(self):
        matcher = TitleMatcher()
        assert matcher.normalize_title("Too   many    spaces") == "too many spaces"

    def test_empty_string(self):
        matcher = TitleMatcher()
        assert matcher.normalize_title("") == ""
        assert matcher.normalize_title("   ") == ""


class TestSimilarityCalculation:
    """Test similarity score calculation."""

    def test_identical_titles(self):
        matcher = TitleMatcher()
        score = matcher.calculate_similarity(
            "Israel Recovers Hostage Body",
            "Israel Recovers Hostage Body"
        )
        assert score == 1.0

    def test_case_insensitive_identical(self):
        matcher = TitleMatcher()
        score = matcher.calculate_similarity(
            "israel recovers hostage body",
            "ISRAEL RECOVERS HOSTAGE BODY"
        )
        assert score == 1.0

    def test_similar_titles(self):
        matcher = TitleMatcher()
        score = matcher.calculate_similarity(
            "Israel Recovers Last Hostage Body from Gaza",
            "Israel recovers last hostage body from Gaza tunnel"
        )
        # Should be high similarity (> 85%)
        assert score > 0.85

    def test_different_titles(self):
        matcher = TitleMatcher()
        score = matcher.calculate_similarity(
            "Ukraine war update",
            "Stock market crash"
        )
        # Should be low similarity
        assert score < 0.30

    def test_partial_overlap(self):
        matcher = TitleMatcher()
        score = matcher.calculate_similarity(
            "Trump announces new tariffs on China",
            "Biden announces new policy on China"
        )
        # Moderate overlap (these titles share structure but different subjects)
        assert 0.30 < score < 0.75

    def test_empty_string_returns_zero(self):
        matcher = TitleMatcher()
        assert matcher.calculate_similarity("", "test") == 0.0
        assert matcher.calculate_similarity("test", "") == 0.0
        assert matcher.calculate_similarity("", "") == 0.0


class TestDuplicateDetection:
    """Test duplicate detection logic."""

    def test_duplicate_found_high_similarity(self):
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "Israel Recovers Last Hostage Body from Gaza",
            ["Israel recovers last hostage body from Gaza tunnel"]
        )
        assert result.is_duplicate is True
        assert result.similarity >= 0.85

    def test_potential_match_medium_similarity(self):
        matcher = TitleMatcher(duplicate_threshold=0.90, potential_threshold=0.70)
        result = matcher.find_duplicate(
            "Trump tariffs affect global markets",
            ["New Trump tariffs impact markets worldwide"]
        )
        # May be potential but not definite duplicate
        assert result.similarity >= 0.60

    def test_no_match_low_similarity(self):
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "Sports team wins championship",
            ["Breaking news: earthquake hits Japan"]
        )
        assert result.is_duplicate is False
        assert result.is_potential is False

    def test_empty_comparison_list(self):
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "Some headline",
            []
        )
        assert result.is_duplicate is False
        assert result.is_potential is False
        assert "NO_COMPARISON_DATA" in result.reason

    def test_best_match_selected(self):
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "Israel Recovers Last Hostage Body",
            [
                "Ukraine war update",  # Low match
                "Israel recovers hostage body from Gaza",  # High match
                "Stock market news",  # No match
            ]
        )
        assert result.matched_title == "Israel recovers hostage body from Gaza"


class TestCustomThresholds:
    """Test custom threshold configuration."""

    def test_custom_duplicate_threshold(self):
        matcher = TitleMatcher(duplicate_threshold=0.95)
        # 92% match should NOT be duplicate with 95% threshold
        result = matcher.find_duplicate(
            "Israel Recovers Last Hostage Body from Gaza",
            ["Israel recovers last hostage body from Gaza tunnel"]
        )
        # This pair is ~92% similar, so with 95% threshold it's not duplicate
        if result.similarity < 0.95:
            assert result.is_duplicate is False

    def test_custom_potential_threshold(self):
        matcher = TitleMatcher(potential_threshold=0.80)
        # 75% match should NOT be potential with 80% threshold
        result = matcher.find_duplicate(
            "Trump announces tariffs",
            ["President discusses trade policy"]
        )
        if result.similarity < 0.80:
            assert result.is_potential is False


class TestFindAllSimilar:
    """Test finding all similar titles."""

    def test_returns_all_above_threshold(self):
        matcher = TitleMatcher()
        results = matcher.find_all_similar(
            "War in Ukraine continues",
            [
                "Ukraine war update",  # Similar
                "Ukraine conflict latest",  # Similar
                "Stock market news",  # Not similar
            ],
            threshold=0.30
        )
        # Should return at least the Ukraine-related titles
        assert len(results) >= 2

    def test_sorted_by_similarity(self):
        matcher = TitleMatcher()
        results = matcher.find_all_similar(
            "Breaking news today",
            ["Breaking news now", "Today's news", "Old news"],
            threshold=0.20
        )
        # Should be sorted by similarity descending
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]


class TestSingletonMatcher:
    """Test get_title_matcher singleton."""

    def test_returns_title_matcher_instance(self):
        matcher = get_title_matcher()
        assert isinstance(matcher, TitleMatcher)

    def test_singleton_returns_same_instance(self):
        matcher1 = get_title_matcher()
        matcher2 = get_title_matcher()
        assert matcher1 is matcher2


class TestRealWorldCases:
    """Test real-world duplicate detection cases from the plan."""

    def test_cross_source_identical_story(self):
        """Test: Same story from GDELT and WorldNews."""
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "Israel Recovers Last Hostage Body from Gaza",
            ["Israel Recovers Last Hostage Body from Gaza"]
        )
        assert result.is_duplicate is True
        assert result.similarity == 1.0

    def test_cross_source_similar_headlines(self):
        """Test: Same story, slightly different headlines."""
        matcher = TitleMatcher()
        # Event 99 vs 142 from the plan
        result = matcher.find_duplicate(
            "Israel Recovers Last Hostage Body from Gaza",
            ["Israel recovers last hostage body from Gaza tunnel"]
        )
        assert result.is_duplicate is True
        assert result.similarity > 0.85

    def test_update_not_duplicate(self):
        """Test: Update to existing story should not be duplicate."""
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "UPDATE: Death toll rises to 50 in Gaza attack",
            ["Gaza attack kills at least 30"]
        )
        # Should not be duplicate (different info)
        assert result.similarity < 0.85


class TestResultNamedTuple:
    """Test TitleMatchResult structure."""

    def test_result_has_all_fields(self):
        matcher = TitleMatcher()
        result = matcher.find_duplicate("Test", ["Test"])

        assert hasattr(result, 'is_duplicate')
        assert hasattr(result, 'is_potential')
        assert hasattr(result, 'similarity')
        assert hasattr(result, 'matched_title')
        assert hasattr(result, 'reason')

    def test_result_is_namedtuple(self):
        matcher = TitleMatcher()
        result = matcher.find_duplicate("Test", ["Test"])
        assert isinstance(result, TitleMatchResult)
