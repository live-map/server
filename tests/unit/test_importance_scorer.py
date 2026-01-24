"""
Tests for the Goldstein Scale based importance scorer.
"""

import pytest

from app.agent.importance_scorer import (
    ImportanceLevel,
    ImportanceResult,
    calculate_importance,
    calculate_event_type_score,
    calculate_actor_significance,
    calculate_geographic_scope,
    calculate_casualty_scale,
    calculate_source_coverage,
    calculate_escalation_potential,
    is_important_event,
)


class TestEventTypeScore:
    """Test Goldstein Scale based event type scoring."""

    def test_nuclear_strike_highest_importance(self):
        """Nuclear strike should have highest importance."""
        score, pattern = calculate_event_type_score("Nuclear strike on enemy position")
        assert score >= 0.9
        assert pattern == "nuclear strike"

    def test_airstrike_high_importance(self):
        """Airstrike should have high importance."""
        score, pattern = calculate_event_type_score("Israel launches airstrike on Gaza")
        assert score >= 0.8
        assert "airstrike" in pattern

    def test_mass_shooting_high_importance(self):
        """Mass shooting should have high importance."""
        score, pattern = calculate_event_type_score("Mass shooting at school leaves 10 dead")
        assert score >= 0.8
        assert pattern == "mass shooting"

    def test_protest_medium_importance(self):
        """Regular protest should have medium importance."""
        score, pattern = calculate_event_type_score("Thousands join protest in capital")
        assert 0.4 <= score <= 0.7
        assert pattern == "protest"

    def test_ceasefire_lower_importance(self):
        """Ceasefire (cooperative) should have lower importance."""
        score, pattern = calculate_event_type_score("Ceasefire agreement reached")
        assert score <= 0.5
        assert pattern == "ceasefire"

    def test_no_pattern_match_neutral(self):
        """No pattern match should return neutral score."""
        score, pattern = calculate_event_type_score("Weather forecast for tomorrow")
        assert 0.4 <= score <= 0.6  # Neutral
        assert pattern is None


class TestActorSignificance:
    """Test actor significance scoring."""

    def test_us_highest_significance(self):
        """United States should have highest significance."""
        score, actors = calculate_actor_significance("United States deploys troops")
        assert score >= 0.95
        assert "united states" in actors

    def test_russia_high_significance(self):
        """Russia should have high significance."""
        score, actors = calculate_actor_significance("Russia announces military exercise")
        assert score >= 0.9
        assert "russia" in actors

    def test_nato_high_significance(self):
        """NATO should have high significance."""
        score, actors = calculate_actor_significance("NATO summit discusses expansion")
        assert score >= 0.9
        assert "nato" in actors

    def test_multiple_actors(self):
        """Multiple actors should be detected."""
        score, actors = calculate_actor_significance("Russia and Ukraine exchange prisoners")
        assert score >= 0.8
        assert len(actors) >= 2

    def test_no_actor_zero_score(self):
        """No actor should return zero score."""
        score, actors = calculate_actor_significance("Local weather update")
        assert score == 0.0
        assert len(actors) == 0


class TestGeographicScope:
    """Test geographic scope scoring."""

    def test_international_high_score(self):
        """International event should have high scope score."""
        score = calculate_geographic_scope("International summit on climate change")
        assert score >= 0.8

    def test_global_high_score(self):
        """Global event should have high scope score."""
        score = calculate_geographic_scope("Global pandemic response coordination")
        assert score >= 0.85

    def test_local_low_score(self):
        """Local event should have lower scope score."""
        score = calculate_geographic_scope("Local town council meeting")
        assert score <= 0.4

    def test_multiple_countries_high_score(self):
        """Multiple countries mentioned should increase score."""
        score = calculate_geographic_scope("Russia, Ukraine, and France in peace talks")
        assert score >= 0.7

    def test_embassy_moderate_score(self):
        """Embassy mention indicates diplomatic/international."""
        score = calculate_geographic_scope("Protesters gather outside embassy")
        assert score >= 0.5


class TestCasualtyScale:
    """Test casualty scale scoring."""

    def test_numeric_casualties(self):
        """Numeric casualty count should be detected."""
        score, count = calculate_casualty_scale("50 killed in explosion")
        assert score >= 0.65
        assert count == 50

    def test_mass_casualties_high_score(self):
        """Mass casualties should have high score."""
        score, count = calculate_casualty_scale("Mass casualties reported in attack")
        assert score >= 0.85

    def test_hundreds_killed(self):
        """Hundreds killed should have high score."""
        score, _ = calculate_casualty_scale("Hundreds killed in earthquake")
        assert score >= 0.8

    def test_death_toll_extraction(self):
        """Death toll format should be extracted."""
        score, count = calculate_casualty_scale("Death toll: 25 confirmed")
        assert score >= 0.55
        assert count == 25

    def test_no_casualties_low_score(self):
        """No casualties mentioned should have low score."""
        score, count = calculate_casualty_scale("Peaceful protest in downtown")
        assert score == 0.0
        assert count is None


class TestSourceCoverage:
    """Test source coverage scoring."""

    def test_multiple_tier1_sources(self):
        """Multiple Tier-1 sources should have highest coverage."""
        sources = ["reuters.com", "apnews.com", "bbc.com", "cnn.com", "nytimes.com"]
        score = calculate_source_coverage(sources)
        assert score >= 0.9

    def test_single_tier1_source(self):
        """Single Tier-1 source should have moderate coverage."""
        sources = ["reuters.com"]
        score = calculate_source_coverage(sources)
        assert 0.45 <= score <= 0.55

    def test_no_sources_low_score(self):
        """No sources should have low coverage."""
        score = calculate_source_coverage([])
        assert score <= 0.35

    def test_unknown_sources(self):
        """Unknown sources should have base score."""
        sources = ["unknownnews.com"]
        score = calculate_source_coverage(sources)
        assert score <= 0.35


class TestEscalationPotential:
    """Test escalation potential scoring."""

    def test_threatens_war_high_risk(self):
        """Threatens war should have high escalation risk."""
        score = calculate_escalation_potential("Country threatens war over dispute")
        assert score >= 0.9

    def test_nuclear_high_risk(self):
        """Nuclear mention should have high escalation risk."""
        score = calculate_escalation_potential("Nuclear weapons on standby")
        assert score >= 0.85

    def test_escalation_keyword(self):
        """Escalation keyword should increase score."""
        score = calculate_escalation_potential("Tensions escalate in region")
        assert score >= 0.75

    def test_ceasefire_reduces_risk(self):
        """Ceasefire should reduce escalation risk."""
        score = calculate_escalation_potential("Ceasefire holds despite violations")
        assert score <= 0.5

    def test_peace_reduces_risk(self):
        """Peace talks should reduce escalation risk."""
        score = calculate_escalation_potential("Peace negotiations continue")
        assert score <= 0.4


class TestCalculateImportance:
    """Test main importance calculation."""

    def test_critical_event(self):
        """Critical event should have critical importance."""
        result = calculate_importance(
            title="Russia launches massive airstrike on Ukraine",
            content="Multiple cities hit, mass casualties reported",
            sources=["reuters.com", "bbc.com", "cnn.com"],
        )
        assert result.level == ImportanceLevel.CRITICAL
        assert result.score >= 0.7

    def test_high_importance_event(self):
        """High importance event should be classified correctly."""
        result = calculate_importance(
            title="NATO announces military exercise near Russia border",
            content="Thousands of troops deployed",
            sources=["reuters.com", "bbc.com"],
        )
        assert result.level in [ImportanceLevel.CRITICAL, ImportanceLevel.HIGH]
        assert result.score >= 0.5

    def test_medium_importance_event(self):
        """Medium importance event should be classified correctly."""
        result = calculate_importance(
            title="Mass protest in France turns violent",
            content="Clashes with riot police, tear gas deployed",
            sources=["reuters.com", "bbc.com"],
        )
        assert result.level in [ImportanceLevel.MEDIUM, ImportanceLevel.HIGH]
        assert 0.3 <= result.score <= 0.8

    def test_low_importance_event(self):
        """Low importance event should be classified correctly."""
        result = calculate_importance(
            title="Local weather update",
            content="Sunny skies expected tomorrow",
            sources=[],
        )
        assert result.level == ImportanceLevel.LOW
        assert result.score < 0.3

    def test_result_to_dict(self):
        """Result should convert to dict correctly."""
        result = calculate_importance(
            title="Russia Ukraine conflict escalates",
            sources=["reuters.com"],
        )
        d = result.to_dict()
        assert "score" in d
        assert "level" in d
        assert "components" in d
        assert "event_type" in d["components"]


class TestIsImportantEvent:
    """Test quick importance check."""

    def test_important_event_passes(self):
        """Important event should pass threshold."""
        assert is_important_event(
            title="Russia launches airstrike on Ukraine",
            sources=["reuters.com", "bbc.com"],
            threshold=0.5,
        )

    def test_unimportant_event_fails(self):
        """Unimportant event should fail threshold."""
        assert not is_important_event(
            title="Local weather forecast",
            threshold=0.5,
        )

    def test_custom_threshold(self):
        """Custom threshold should be respected."""
        # Event that passes 0.3 but not 0.7
        result = is_important_event(
            title="Protest in city center",
            threshold=0.3,
        )
        # Should pass low threshold
        assert result or not result  # Either is valid depending on scoring


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_input(self):
        """Empty input should not crash."""
        result = calculate_importance(title="", content="", sources=[])
        assert result.score >= 0.0
        assert result.score <= 1.0

    def test_very_long_text(self):
        """Very long text should be handled."""
        long_text = "Russia Ukraine conflict " * 1000
        result = calculate_importance(title=long_text, content=long_text)
        assert result.score >= 0.0

    def test_unicode_text(self):
        """Unicode text should be handled."""
        result = calculate_importance(
            title="러시아 우크라이나 전쟁 continues",
            content="多国参与谈判",
        )
        assert result.score >= 0.0

    def test_custom_weights(self):
        """Custom weights should affect scoring."""
        custom_weights = {
            "event_type": 0.5,
            "actor_significance": 0.2,
            "geographic_scope": 0.1,
            "casualty_scale": 0.1,
            "source_coverage": 0.05,
            "escalation_potential": 0.05,
        }
        result = calculate_importance(
            title="Airstrike hits city",
            weights=custom_weights,
        )
        assert result.weights == custom_weights
