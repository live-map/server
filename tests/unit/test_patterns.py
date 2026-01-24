"""
Tests for the centralized patterns module (P2).
"""

import pytest

from app.agent.patterns import (
    # Pattern lists
    NOT_EVENT_PATTERNS,
    ENTERTAINMENT_PATTERNS,
    SPORTS_NEWS_PATTERNS,
    LOCAL_CRIME_PATTERNS,
    INTERNATIONAL_AFFAIRS_KEYWORDS,
    BREAKING_KEYWORDS,

    # Compiled patterns
    COMPILED_NOT_EVENT_PATTERNS,
    COMPILED_ENTERTAINMENT_PATTERNS,
    COMPILED_SPORTS_PATTERNS,
    COMPILED_LOCAL_CRIME_PATTERNS,
    COMPILED_BREAKING_PATTERNS,
    COMPILED_SIGNIFICANCE_PATTERNS,

    # Helper functions
    matches_any_pattern,
    get_matching_patterns,
    count_pattern_matches,
    is_international_affair,
)


class TestPatternLists:
    """Test pattern list definitions."""

    def test_not_event_patterns_exist(self):
        """NOT_EVENT_PATTERNS should have entries."""
        assert len(NOT_EVENT_PATTERNS) > 0

    def test_entertainment_patterns_exist(self):
        """ENTERTAINMENT_PATTERNS should have entries."""
        assert len(ENTERTAINMENT_PATTERNS) > 0

    def test_sports_patterns_exist(self):
        """SPORTS_NEWS_PATTERNS should have entries."""
        assert len(SPORTS_NEWS_PATTERNS) > 0

    def test_local_crime_patterns_exist(self):
        """LOCAL_CRIME_PATTERNS should have entries."""
        assert len(LOCAL_CRIME_PATTERNS) > 0

    def test_international_keywords_have_categories(self):
        """INTERNATIONAL_AFFAIRS_KEYWORDS should have category keys."""
        expected_categories = ["war", "conflict", "politics", "security", "military", "terrorism", "diplomacy", "protest"]
        for cat in expected_categories:
            assert cat in INTERNATIONAL_AFFAIRS_KEYWORDS
            assert len(INTERNATIONAL_AFFAIRS_KEYWORDS[cat]) > 0

    def test_breaking_keywords_exist(self):
        """BREAKING_KEYWORDS should have entries."""
        assert len(BREAKING_KEYWORDS) > 0
        assert "breaking" in BREAKING_KEYWORDS


class TestCompiledPatterns:
    """Test compiled pattern lists."""

    def test_compiled_not_event_patterns(self):
        """Compiled NOT_EVENT_PATTERNS should match correctly."""
        text = "The event will be held next week"
        assert matches_any_pattern(text, COMPILED_NOT_EVENT_PATTERNS)

    def test_compiled_entertainment_patterns(self):
        """Compiled ENTERTAINMENT_PATTERNS should match correctly."""
        text = "The movie premiere was a success"
        assert matches_any_pattern(text, COMPILED_ENTERTAINMENT_PATTERNS)

    def test_compiled_sports_patterns(self):
        """Compiled SPORTS_PATTERNS should match correctly."""
        text = "Team wins championship tournament"
        assert matches_any_pattern(text, COMPILED_SPORTS_PATTERNS)

    def test_compiled_local_crime_patterns(self):
        """Compiled LOCAL_CRIME_PATTERNS should match correctly."""
        text = "Police arrested suspect in robbery case"
        assert matches_any_pattern(text, COMPILED_LOCAL_CRIME_PATTERNS)

    def test_compiled_breaking_patterns(self):
        """Compiled BREAKING_PATTERNS should match correctly."""
        text = "BREAKING: Major event occurs"
        assert matches_any_pattern(text, COMPILED_BREAKING_PATTERNS)


class TestMatchesAnyPattern:
    """Test matches_any_pattern function."""

    def test_matches_when_pattern_found(self):
        """Should return True when pattern matches."""
        text = "This is a movie premiere event"
        assert matches_any_pattern(text, COMPILED_ENTERTAINMENT_PATTERNS)

    def test_no_match_when_no_pattern_found(self):
        """Should return False when no pattern matches."""
        text = "Military conflict in region"
        assert not matches_any_pattern(text, COMPILED_ENTERTAINMENT_PATTERNS)

    def test_case_insensitive_matching(self):
        """Should match case-insensitively."""
        text = "MOVIE PREMIERE tonight"
        assert matches_any_pattern(text, COMPILED_ENTERTAINMENT_PATTERNS)


class TestGetMatchingPatterns:
    """Test get_matching_patterns function."""

    def test_returns_matched_patterns(self):
        """Should return list of matched patterns."""
        text = "Breaking news about a celebrity movie premiere"
        matches = get_matching_patterns(text, COMPILED_ENTERTAINMENT_PATTERNS)
        assert len(matches) > 0

    def test_returns_empty_when_no_matches(self):
        """Should return empty list when no matches."""
        text = "Military operations continue"
        matches = get_matching_patterns(text, COMPILED_ENTERTAINMENT_PATTERNS)
        assert len(matches) == 0


class TestCountPatternMatches:
    """Test count_pattern_matches function."""

    def test_counts_multiple_matches(self):
        """Should count multiple pattern matches."""
        text = "Celebrity actor singer at concert event"
        count = count_pattern_matches(text, COMPILED_ENTERTAINMENT_PATTERNS)
        assert count >= 2  # Should match multiple entertainment patterns

    def test_counts_zero_when_no_matches(self):
        """Should return 0 when no matches."""
        text = "Military troops deployed"
        count = count_pattern_matches(text, COMPILED_ENTERTAINMENT_PATTERNS)
        assert count == 0


class TestIsInternationalAffair:
    """Test is_international_affair function."""

    def test_war_is_international(self):
        """War content should be international affair."""
        is_intl, category = is_international_affair("Russia invades Ukraine with military troops")
        assert is_intl
        assert category in ["war", "military", "conflict"]

    def test_terrorism_is_international(self):
        """Terrorism content should be international affair."""
        is_intl, category = is_international_affair("Terrorist attack in city center")
        assert is_intl
        assert category == "terrorism"

    def test_diplomacy_is_international(self):
        """Diplomacy content should be international affair."""
        is_intl, category = is_international_affair("UN summit discusses peace treaty")
        assert is_intl
        assert category in ["diplomacy", "politics"]  # Both are valid for "summit"

    def test_sports_is_not_international(self):
        """Sports content should not be international affair."""
        is_intl, category = is_international_affair("Team wins championship tournament final")
        assert not is_intl
        assert category == "sports"

    def test_local_crime_is_not_international(self):
        """Local crime should not be international affair."""
        is_intl, category = is_international_affair("Police arrested suspect in robbery")
        assert not is_intl
        assert category == "crime"

    def test_entertainment_is_not_international(self):
        """Entertainment should not be international affair."""
        is_intl, category = is_international_affair("Celebrity movie premiere tonight")
        assert not is_intl
        assert category == "entertainment"


class TestSignificancePatterns:
    """Test significance indicator patterns."""

    def test_international_indicator(self):
        """Should match international indicators."""
        text = "International summit on security"
        assert matches_any_pattern(text, COMPILED_SIGNIFICANCE_PATTERNS)

    def test_mass_casualty_indicator(self):
        """Should match mass casualty indicators."""
        text = "Hundreds of people affected"
        assert matches_any_pattern(text, COMPILED_SIGNIFICANCE_PATTERNS)

    def test_government_indicator(self):
        """Should match government indicators."""
        text = "Government officials respond"
        assert matches_any_pattern(text, COMPILED_SIGNIFICANCE_PATTERNS)


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_text(self):
        """Should handle empty text."""
        assert not matches_any_pattern("", COMPILED_ENTERTAINMENT_PATTERNS)
        is_intl, category = is_international_affair("")
        assert not is_intl

    def test_special_characters(self):
        """Should handle special characters."""
        text = "Movie!!! @premiere #celebrity"
        assert matches_any_pattern(text, COMPILED_ENTERTAINMENT_PATTERNS)

    def test_unicode_text(self):
        """Should handle unicode text."""
        text = "러시아 invasion 우크라이나"
        is_intl, category = is_international_affair(text)
        assert is_intl  # "invasion" should match
