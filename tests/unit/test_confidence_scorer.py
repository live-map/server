"""
Unit tests for Multi-Source Confidence Scorer.

Tests the confidence scoring system including:
1. Base score calculation (source count)
2. Tier weight averaging
3. Diversity bonus
4. Two-Source Rule
5. Publication recommendations
"""

import pytest

from app.agent.confidence_scorer import (
    MultiSourceConfidenceScorer,
    ConfidenceResult,
    ConfidenceLevel,
    PublishRecommendation,
    TIER_WEIGHTS,
    calculate_confidence,
)
from app.agent.triggers.base import SourceTier


class TestBaseScoreCalculation:
    """Tests for base score from source count."""

    def test_zero_sources(self):
        """Zero sources should return 0.0 score."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence([])

        assert result.score == 0.0
        assert result.source_count == 0
        assert result.level == ConfidenceLevel.LOW
        assert result.recommendation == PublishRecommendation.DO_NOT_PUBLISH
        assert not result.two_source_satisfied

    def test_single_source_base_score(self, single_gdelt_source):
        """Single source should have base score 0.50."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_gdelt_source)

        assert result.source_count == 1
        assert result.base_score == 0.50

    def test_two_sources_base_score(self, gdelt_plus_reddit_sources):
        """Two sources should have base score 0.70."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        assert result.source_count == 2
        assert result.base_score == 0.70

    def test_three_sources_base_score(self, three_tier_sources):
        """Three+ sources should have base score 0.85."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(three_tier_sources)

        assert result.source_count == 3
        assert result.base_score == 0.85


class TestTierWeighting:
    """Tests for tier-based credibility weighting."""

    def test_tier1_govt_weight(self):
        """Tier-1 government source should have weight 0.99."""
        assert TIER_WEIGHTS[SourceTier.TIER1_GOVT.value] == 0.99

    def test_tier1_news_weight(self):
        """Tier-1 news source should have weight 0.90."""
        assert TIER_WEIGHTS[SourceTier.TIER1_NEWS.value] == 0.90

    def test_tier2_data_weight(self):
        """Tier-2 data source should have weight 0.85."""
        assert TIER_WEIGHTS[SourceTier.TIER2_DATA.value] == 0.85

    def test_tier2_news_weight(self):
        """Tier-2 news source should have weight 0.75."""
        assert TIER_WEIGHTS[SourceTier.TIER2_NEWS.value] == 0.75

    def test_tier3_social_weight(self):
        """Tier-3 social source should have weight 0.40."""
        assert TIER_WEIGHTS[SourceTier.TIER3_SOCIAL.value] == 0.40

    def test_tier3_msg_weight(self):
        """Tier-3 messaging source should have weight 0.35."""
        assert TIER_WEIGHTS[SourceTier.TIER3_MSG.value] == 0.35

    def test_tier3_trend_weight(self):
        """Tier-3 trend source should have weight 0.30."""
        assert TIER_WEIGHTS[SourceTier.TIER3_TREND.value] == 0.30

    def test_tier_average_single_source(self, single_gdelt_source):
        """Single GDELT should have tier average 0.90."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_gdelt_source)

        assert result.tier_average == 0.90

    def test_tier_average_multi_source(self, gdelt_plus_reddit_sources):
        """GDELT + Reddit tier average should be (0.90 + 0.40) / 2 = 0.65."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        expected_avg = (0.90 + 0.40) / 2  # 0.65
        assert abs(result.tier_average - expected_avg) < 0.01


class TestDiversityBonus:
    """Tests for source diversity bonus."""

    def test_single_tier_no_bonus(self, single_gdelt_source):
        """Single tier should have no diversity bonus."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_gdelt_source)

        assert result.diversity_bonus == 0.0

    def test_two_tiers_bonus(self, gdelt_plus_reddit_sources):
        """Two different tiers should have 0.03 bonus."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        # tier1 + tier3 = 2 tiers, (2-1) * 0.03 = 0.03
        assert result.diversity_bonus == 0.03

    def test_three_tiers_bonus(self, three_tier_sources):
        """Three different tiers should have 0.06 bonus."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(three_tier_sources)

        # tier1 + tier2 + tier3 = 3 tiers, (3-1) * 0.03 = 0.06
        assert result.diversity_bonus == 0.06


class TestConfidenceScoreCalculation:
    """Tests for final confidence score calculation."""

    def test_single_gdelt_score(self, single_gdelt_source):
        """Single GDELT: base(0.50)*0.5 + tier(0.90)*0.5 + div(0) = 0.70."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_gdelt_source)

        expected = (0.50 * 0.5) + (0.90 * 0.5) + 0.0  # 0.70
        assert abs(result.score - expected) < 0.01
        assert abs(result.score - 0.70) < 0.01

    def test_single_usgs_govt_score(self, single_usgs_source):
        """Single USGS (govt): base(0.50)*0.5 + tier(0.99)*0.5 + div(0) = 0.745."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_usgs_source)

        expected = (0.50 * 0.5) + (0.99 * 0.5) + 0.0  # 0.745
        assert abs(result.score - expected) < 0.01
        # Should be ~0.74-0.75 range
        assert 0.74 <= result.score <= 0.75

    def test_gdelt_plus_reddit_score(self, gdelt_plus_reddit_sources):
        """GDELT + Reddit: base(0.70)*0.5 + tier(0.65)*0.5 + div(0.03) = 0.705."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        tier_avg = (0.90 + 0.40) / 2  # 0.65
        expected = (0.70 * 0.5) + (tier_avg * 0.5) + 0.03  # 0.705
        assert abs(result.score - expected) < 0.01
        # Should exceed 0.70 threshold
        assert result.score >= 0.70

    def test_three_source_high_score(self, three_tier_sources):
        """Three-tier sources should have high score (0.83+)."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(three_tier_sources)

        # base(0.85)*0.5 + tier_avg*0.5 + div(0.06)
        tier_avg = (0.90 + 0.75 + 0.40) / 3  # ~0.683
        expected = (0.85 * 0.5) + (tier_avg * 0.5) + 0.06
        assert abs(result.score - expected) < 0.01
        # Should be in HIGH or VERY_HIGH range
        assert result.score >= 0.80

    def test_reddit_only_low_score(self, single_reddit_source):
        """Reddit-only should have low score (< 0.70)."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_reddit_source)

        # base(0.50)*0.5 + tier(0.40)*0.5 + div(0) = 0.45
        expected = (0.50 * 0.5) + (0.40 * 0.5) + 0.0  # 0.45
        assert abs(result.score - expected) < 0.01
        assert result.score < 0.70
        assert result.level == ConfidenceLevel.LOW

    def test_score_capped_at_099(self):
        """Score should be capped at 0.99."""
        scorer = MultiSourceConfidenceScorer()
        # Create a very high scoring scenario
        sources = [
            {"name": "USGS", "tier": SourceTier.TIER1_GOVT.value},
            {"name": "NOAA", "tier": SourceTier.TIER1_GOVT.value},
            {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "Currents", "tier": SourceTier.TIER2_NEWS.value},
            {"name": "Reddit", "tier": SourceTier.TIER3_SOCIAL.value},
        ]
        result = scorer.calculate_confidence(sources)

        assert result.score <= 0.99


class TestTwoSourceRule:
    """Tests for Two-Source Rule journalism standard."""

    def test_two_source_not_satisfied_single(self, single_gdelt_source):
        """Single non-govt source should not satisfy Two-Source Rule."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_gdelt_source)

        assert not result.two_source_satisfied

    def test_two_source_satisfied_single_govt(self, single_usgs_source):
        """Single Tier-1 govt source should satisfy Two-Source Rule."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_usgs_source)

        # Single govt source is sufficient (official data)
        assert result.two_source_satisfied

    def test_two_source_satisfied_multi(self, gdelt_plus_reddit_sources):
        """Two+ sources should satisfy Two-Source Rule."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        assert result.two_source_satisfied

    def test_two_source_satisfied_three(self, three_tier_sources):
        """Three sources should definitely satisfy Two-Source Rule."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(three_tier_sources)

        assert result.two_source_satisfied


class TestConfidenceLevels:
    """Tests for confidence level classification."""

    def test_level_low(self, single_reddit_source):
        """Score < 0.50 should be LOW."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_reddit_source)

        # Reddit only gives ~0.45
        assert result.level == ConfidenceLevel.LOW

    def test_level_medium(self):
        """Score 0.50-0.69 should be MEDIUM."""
        scorer = MultiSourceConfidenceScorer()
        # Create source with tier2_news to get medium score
        sources = [{"name": "Currents", "tier": SourceTier.TIER2_NEWS.value}]
        result = scorer.calculate_confidence(sources)

        # Single Tier-2 news: 0.50*0.5 + 0.75*0.5 = 0.625
        assert result.level == ConfidenceLevel.MEDIUM

    def test_level_high(self, gdelt_plus_reddit_sources):
        """Score 0.70-0.84 should be HIGH."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        assert result.level == ConfidenceLevel.HIGH

    def test_level_very_high(self, three_tier_sources):
        """Score 0.85+ should be VERY_HIGH."""
        scorer = MultiSourceConfidenceScorer()
        # Add another source to push score higher
        sources = three_tier_sources + [
            {"name": "USGS", "tier": SourceTier.TIER1_GOVT.value}
        ]
        result = scorer.calculate_confidence(sources)

        # With 4 sources including govt, should be very high
        assert result.score >= 0.85
        assert result.level == ConfidenceLevel.VERY_HIGH


class TestPublishRecommendations:
    """Tests for publication recommendations."""

    def test_do_not_publish_low(self, single_reddit_source):
        """LOW confidence should recommend DO_NOT_PUBLISH."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_reddit_source)

        assert result.recommendation == PublishRecommendation.DO_NOT_PUBLISH

    def test_review_required_medium(self):
        """MEDIUM confidence should recommend REVIEW_REQUIRED."""
        scorer = MultiSourceConfidenceScorer()
        sources = [{"name": "Currents", "tier": SourceTier.TIER2_NEWS.value}]
        result = scorer.calculate_confidence(sources)

        assert result.recommendation == PublishRecommendation.REVIEW_REQUIRED

    def test_publishable_high(self, gdelt_plus_reddit_sources):
        """HIGH confidence should recommend PUBLISHABLE."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(gdelt_plus_reddit_sources)

        assert result.recommendation == PublishRecommendation.PUBLISHABLE

    def test_immediate_publish_very_high(self):
        """VERY_HIGH confidence should recommend IMMEDIATE_PUBLISH."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "Reuters", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "Currents", "tier": SourceTier.TIER2_NEWS.value},
            {"name": "Reddit", "tier": SourceTier.TIER3_SOCIAL.value},
        ]
        result = scorer.calculate_confidence(sources)

        # Should be very high with 4 sources
        assert result.recommendation == PublishRecommendation.IMMEDIATE_PUBLISH

    def test_govt_source_immediate_publish(self, single_usgs_source):
        """Single govt source should always recommend IMMEDIATE_PUBLISH."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(single_usgs_source)

        # Govt sources bypass normal thresholds
        assert result.recommendation == PublishRecommendation.IMMEDIATE_PUBLISH


class TestIsPublishable:
    """Tests for quick publishability check."""

    def test_is_publishable_true(self, gdelt_plus_reddit_sources):
        """Multi-source should be publishable."""
        scorer = MultiSourceConfidenceScorer()
        assert scorer.is_publishable(gdelt_plus_reddit_sources)

    def test_is_publishable_false(self, single_reddit_source):
        """Single social source should not be publishable."""
        scorer = MultiSourceConfidenceScorer()
        assert not scorer.is_publishable(single_reddit_source)

    def test_is_publishable_custom_threshold(self, single_reddit_source):
        """Custom threshold should affect publishability."""
        scorer = MultiSourceConfidenceScorer(min_publish_confidence=0.40)
        # Reddit gives ~0.45, should pass with 0.40 threshold
        assert scorer.is_publishable(single_reddit_source)


class TestGetRequiredSources:
    """Tests for source recommendation."""

    def test_sufficient_sources(self, three_tier_sources):
        """Should indicate sufficient sources."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.get_required_sources(three_tier_sources)

        assert "Sufficient" in result

    def test_need_additional_sources(self, single_reddit_source):
        """Should recommend additional sources."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.get_required_sources(single_reddit_source)

        assert "Need" in result


class TestConfidenceResultSerialization:
    """Tests for ConfidenceResult serialization."""

    def test_to_dict(self, three_tier_sources):
        """Result should serialize to dict correctly."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence(three_tier_sources)
        data = result.to_dict()

        assert "score" in data
        assert "level" in data
        assert "recommendation" in data
        assert "components" in data
        assert "sources" in data
        assert "tier_types" in data
        assert "two_source_satisfied" in data

        # Check component structure
        assert "source_count" in data["components"]
        assert "base_score" in data["components"]
        assert "tier_average" in data["components"]
        assert "diversity_bonus" in data["components"]


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_calculate_confidence_function(self, three_tier_sources):
        """Convenience function should work correctly."""
        result = calculate_confidence(three_tier_sources)

        assert isinstance(result, ConfidenceResult)
        assert result.score > 0


class TestCustomTierWeights:
    """Tests for custom tier weights."""

    def test_custom_weights(self):
        """Custom weights should be used."""
        custom_weights = {
            SourceTier.TIER1_NEWS.value: 1.00,  # Override
            SourceTier.TIER3_SOCIAL.value: 0.50,  # Override
        }
        scorer = MultiSourceConfidenceScorer(tier_weights=custom_weights)
        sources = [{"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value}]

        result = scorer.calculate_confidence(sources)

        # Should use custom weight 1.00 instead of default 0.90
        assert result.tier_average == 1.00


class TestDuplicateSourceHandling:
    """Tests for duplicate source handling."""

    def test_duplicate_sources_counted_once(self):
        """Duplicate sources should be deduplicated."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},  # Duplicate
        ]

        result = scorer.calculate_confidence(sources)

        # Should count as 1 source, not 2
        assert result.source_count == 1
        assert result.base_score == 0.50


class TestDomainDiversityVerification:
    """Tests for domain diversity verification in Two-Source Rule."""

    def test_different_domains_is_diverse(self):
        """Sources from different domains should be diverse."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters", "tier": SourceTier.TIER1_NEWS.value, "url": "https://www.reuters.com/article/123"},
            {"name": "AP", "tier": SourceTier.TIER1_NEWS.value, "url": "https://apnews.com/article/456"},
        ]

        is_diverse, count = scorer.check_domain_diversity(sources)

        assert is_diverse is True
        assert count == 2

    def test_same_domain_not_diverse(self):
        """Sources from the same domain should not be diverse."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters1", "tier": SourceTier.TIER1_NEWS.value, "url": "https://www.reuters.com/article/123"},
            {"name": "Reuters2", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/456"},
        ]

        is_diverse, count = scorer.check_domain_diversity(sources)

        assert is_diverse is False
        assert count == 1

    def test_www_prefix_normalized(self):
        """www prefix should be normalized."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "BBC1", "tier": SourceTier.TIER1_NEWS.value, "url": "https://www.bbc.com/article/123"},
            {"name": "BBC2", "tier": SourceTier.TIER1_NEWS.value, "url": "https://bbc.com/article/456"},
        ]

        is_diverse, count = scorer.check_domain_diversity(sources)

        assert is_diverse is False  # Same domain (bbc)
        assert count == 1

    def test_domain_key_used(self):
        """Domain key should be used if URL is not provided."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters", "tier": SourceTier.TIER1_NEWS.value, "domain": "reuters.com"},
            {"name": "AP", "tier": SourceTier.TIER1_NEWS.value, "domain": "apnews.com"},
        ]

        is_diverse, count = scorer.check_domain_diversity(sources)

        assert is_diverse is True
        assert count == 2

    def test_name_fallback_for_diversity(self):
        """Name should be used as fallback if no URL or domain."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "AP", "tier": SourceTier.TIER1_NEWS.value},
        ]

        is_diverse, count = scorer.check_domain_diversity(sources)

        assert is_diverse is True
        assert count == 2

    def test_two_source_rule_requires_domain_diversity(self):
        """Two-Source Rule should require domain diversity by default."""
        scorer = MultiSourceConfidenceScorer()
        # Two sources from same domain
        sources = [
            {"name": "Reuters1", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/123"},
            {"name": "Reuters2", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/456"},
        ]

        result = scorer.calculate_confidence(sources)

        # Should NOT satisfy two-source rule due to same domain
        assert result.two_source_satisfied is False
        assert result.domain_diverse is False

    def test_two_source_satisfied_with_diverse_domains(self):
        """Two-Source Rule should be satisfied with diverse domains."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/123"},
            {"name": "AP", "tier": SourceTier.TIER1_NEWS.value, "url": "https://apnews.com/article/456"},
        ]

        result = scorer.calculate_confidence(sources)

        assert result.two_source_satisfied is True
        assert result.domain_diverse is True
        assert result.unique_domains == 2

    def test_result_includes_domain_diversity_info(self):
        """ConfidenceResult should include domain diversity information."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/123"},
            {"name": "AP", "tier": SourceTier.TIER1_NEWS.value, "url": "https://apnews.com/article/456"},
        ]

        result = scorer.calculate_confidence(sources)
        data = result.to_dict()

        assert "domain_diversity" in data
        assert "unique_domains" in data["domain_diversity"]
        assert "domain_diverse" in data["domain_diversity"]
        assert data["domain_diversity"]["unique_domains"] == 2
        assert data["domain_diversity"]["domain_diverse"] is True

    def test_bbc_uk_and_com_same_domain(self):
        """bbc.co.uk and bbc.com should be normalized to same domain."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "BBC UK", "tier": SourceTier.TIER1_NEWS.value, "url": "https://www.bbc.co.uk/news/123"},
            {"name": "BBC Intl", "tier": SourceTier.TIER1_NEWS.value, "url": "https://www.bbc.com/news/456"},
        ]

        is_diverse, count = scorer.check_domain_diversity(sources)

        # Both should normalize to "bbc"
        assert is_diverse is False
        assert count == 1

    def test_single_govt_source_bypasses_domain_check(self):
        """Single Tier-1 govt source should satisfy rule regardless of domain."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "USGS", "tier": SourceTier.TIER1_GOVT.value, "url": "https://earthquake.usgs.gov/123"},
        ]

        result = scorer.calculate_confidence(sources)

        # Single govt source bypasses two-source requirement
        assert result.two_source_satisfied is True

    def test_mixed_sources_with_duplicates(self):
        """Mixed sources with some duplicates should be handled correctly."""
        scorer = MultiSourceConfidenceScorer()
        sources = [
            {"name": "Reuters1", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/123"},
            {"name": "Reuters2", "tier": SourceTier.TIER1_NEWS.value, "url": "https://reuters.com/article/456"},
            {"name": "AP", "tier": SourceTier.TIER1_NEWS.value, "url": "https://apnews.com/article/789"},
        ]

        result = scorer.calculate_confidence(sources)

        # Should have 2 unique domains (reuters, apnews)
        assert result.unique_domains == 2
        assert result.domain_diverse is True
        assert result.two_source_satisfied is True
