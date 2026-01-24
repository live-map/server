"""
Unit tests for Source Tier system.

Tests domain-based credibility tiers for single-source publishing.
"""

import pytest
from app.agent.source_tiers import (
    DomainTier,
    TIER_1_DOMAINS,
    TIER_2_DOMAINS,
    TIER_3_DOMAINS,
    normalize_domain,
    get_domain_tier,
    get_domain_tier_info,
    get_min_sources_required,
    is_single_source_allowed,
    get_credibility_weight,
    evaluate_source_mix,
    get_tier_statistics,
)


class TestDomainNormalization:
    """Tests for domain normalization."""

    def test_normalize_url(self):
        """URL should be normalized to domain."""
        assert normalize_domain("https://www.reuters.com/world/article") == "reuters.com"

    def test_normalize_removes_www(self):
        """www prefix should be removed."""
        assert normalize_domain("www.bbc.com") == "bbc.com"

    def test_normalize_removes_news_subdomain(self):
        """news. subdomain should be removed."""
        assert normalize_domain("https://news.bbc.co.uk/article") == "bbc.co.uk"

    def test_normalize_removes_mobile_subdomain(self):
        """m. subdomain should be removed."""
        assert normalize_domain("https://m.reuters.com/article") == "reuters.com"

    def test_normalize_removes_edition_subdomain(self):
        """edition. subdomain should be removed."""
        assert normalize_domain("https://edition.cnn.com/article") == "cnn.com"

    def test_normalize_simple_domain(self):
        """Simple domain should pass through."""
        assert normalize_domain("reuters.com") == "reuters.com"


class TestTier1Domains:
    """Tests for Tier-1 (wire services) classification."""

    def test_reuters_is_tier1(self):
        """Reuters should be Tier-1."""
        assert get_domain_tier("reuters.com") == DomainTier.TIER_1

    def test_apnews_is_tier1(self):
        """AP News should be Tier-1."""
        assert get_domain_tier("apnews.com") == DomainTier.TIER_1

    def test_afp_is_tier1(self):
        """AFP should be Tier-1."""
        assert get_domain_tier("afp.com") == DomainTier.TIER_1

    def test_un_is_tier1(self):
        """UN should be Tier-1."""
        assert get_domain_tier("un.org") == DomainTier.TIER_1

    def test_who_is_tier1(self):
        """WHO should be Tier-1."""
        assert get_domain_tier("who.int") == DomainTier.TIER_1

    def test_tier1_single_source_allowed(self):
        """Tier-1 sources should allow single-source publishing."""
        assert is_single_source_allowed("reuters.com") is True
        assert is_single_source_allowed("apnews.com") is True

    def test_tier1_min_sources_is_1(self):
        """Tier-1 sources should require only 1 source."""
        assert get_min_sources_required("reuters.com") == 1
        assert get_min_sources_required("apnews.com") == 1


class TestTier2Domains:
    """Tests for Tier-2 (major outlets) classification."""

    def test_bbc_is_tier2(self):
        """BBC should be Tier-2."""
        assert get_domain_tier("bbc.com") == DomainTier.TIER_2

    def test_nytimes_is_tier2(self):
        """NY Times should be Tier-2."""
        assert get_domain_tier("nytimes.com") == DomainTier.TIER_2

    def test_guardian_is_tier2(self):
        """Guardian should be Tier-2."""
        assert get_domain_tier("theguardian.com") == DomainTier.TIER_2

    def test_cnn_is_tier2(self):
        """CNN should be Tier-2."""
        assert get_domain_tier("cnn.com") == DomainTier.TIER_2

    def test_aljazeera_is_tier2(self):
        """Al Jazeera should be Tier-2."""
        assert get_domain_tier("aljazeera.com") == DomainTier.TIER_2

    def test_tier2_single_source_allowed(self):
        """Tier-2 sources should allow single-source publishing with verification."""
        assert is_single_source_allowed("bbc.com") is True
        assert is_single_source_allowed("nytimes.com") is True

    def test_tier2_min_sources_is_1(self):
        """Tier-2 sources should require only 1 source (with verification)."""
        assert get_min_sources_required("bbc.com") == 1


class TestTier3Domains:
    """Tests for Tier-3 (regional) classification."""

    def test_latimes_is_tier3(self):
        """LA Times should be Tier-3."""
        assert get_domain_tier("latimes.com") == DomainTier.TIER_3

    def test_tier3_single_source_not_allowed(self):
        """Tier-3 sources should NOT allow single-source publishing."""
        assert is_single_source_allowed("latimes.com") is False

    def test_tier3_min_sources_is_2(self):
        """Tier-3 sources should require 2 sources."""
        assert get_min_sources_required("latimes.com") == 2


class TestTier4Domains:
    """Tests for Tier-4 (unknown/other) classification."""

    def test_unknown_domain_is_tier4(self):
        """Unknown domain should be Tier-4."""
        assert get_domain_tier("unknown-blog.com") == DomainTier.TIER_4

    def test_tier4_single_source_not_allowed(self):
        """Tier-4 sources should NOT allow single-source publishing."""
        assert is_single_source_allowed("random-blog.net") is False

    def test_tier4_min_sources_is_3(self):
        """Tier-4 sources should require 3 sources."""
        assert get_min_sources_required("random-blog.net") == 3


class TestCredibilityWeight:
    """Tests for credibility weight calculation."""

    def test_tier1_weight(self):
        """Tier-1 should have weight 0.95."""
        assert get_credibility_weight("reuters.com") == 0.95

    def test_tier2_weight(self):
        """Tier-2 should have weight 0.85."""
        assert get_credibility_weight("bbc.com") == 0.85

    def test_tier3_weight(self):
        """Tier-3 should have weight 0.70."""
        assert get_credibility_weight("latimes.com") == 0.70

    def test_tier4_weight(self):
        """Tier-4 should have weight 0.50."""
        assert get_credibility_weight("random-blog.net") == 0.50


class TestDomainTierInfo:
    """Tests for detailed domain tier info."""

    def test_tier_info_includes_domain(self):
        """Tier info should include normalized domain."""
        info = get_domain_tier_info("https://www.reuters.com/article")
        assert info.domain == "reuters.com"

    def test_tier_info_includes_tier(self):
        """Tier info should include tier classification."""
        info = get_domain_tier_info("reuters.com")
        assert info.tier == DomainTier.TIER_1

    def test_tier_info_includes_min_sources(self):
        """Tier info should include min sources required."""
        info = get_domain_tier_info("reuters.com")
        assert info.min_sources_required == 1

    def test_tier_info_includes_verification_delay(self):
        """Tier info should include verification delay."""
        info = get_domain_tier_info("bbc.com")
        assert info.verification_delay_minutes == 60


class TestEvaluateSourceMix:
    """Tests for source mix evaluation."""

    def test_tier1_single_source_can_publish(self):
        """Single Tier-1 source should allow publishing."""
        sources = [{"url": "https://reuters.com/article/123"}]
        result = evaluate_source_mix(sources)

        assert result["can_publish"] is True
        assert result["recommended_action"] == "PUBLISH_IMMEDIATE"

    def test_tier2_single_source_can_publish_with_verification(self):
        """Single Tier-2 source should allow publishing with verification."""
        sources = [{"url": "https://bbc.com/news/123"}]
        result = evaluate_source_mix(sources)

        assert result["can_publish"] is True
        assert result["recommended_action"] == "PUBLISH_WITH_VERIFICATION"
        assert result["verification_required"] is True
        assert result["verification_delay_minutes"] == 60

    def test_tier3_single_source_cannot_publish(self):
        """Single Tier-3 source should NOT allow publishing."""
        sources = [{"url": "https://latimes.com/news/123"}]
        result = evaluate_source_mix(sources)

        assert result["can_publish"] is False
        assert result["recommended_action"] == "NEED_MORE_SOURCES"

    def test_tier4_single_source_cannot_publish(self):
        """Single Tier-4 source should NOT allow publishing."""
        sources = [{"url": "https://random-blog.com/post/123"}]
        result = evaluate_source_mix(sources)

        assert result["can_publish"] is False
        assert result["recommended_action"] == "NEED_MORE_SOURCES"

    def test_two_diverse_sources_can_publish(self):
        """Two sources from different domains should allow publishing."""
        sources = [
            {"url": "https://latimes.com/news/123"},
            {"url": "https://chicagotribune.com/news/456"},
        ]
        result = evaluate_source_mix(sources)

        assert result["can_publish"] is True
        assert result["recommended_action"] == "PUBLISH_STANDARD"

    def test_empty_sources_cannot_publish(self):
        """Empty sources should not allow publishing."""
        result = evaluate_source_mix([])

        assert result["can_publish"] is False
        assert result["recommended_action"] == "REJECT"


class TestTierStatistics:
    """Tests for tier statistics."""

    def test_tier_stats_returns_counts(self):
        """Stats should return counts for each tier."""
        stats = get_tier_statistics()

        assert "tier_1_count" in stats
        assert "tier_2_count" in stats
        assert "tier_3_count" in stats
        assert stats["tier_1_count"] > 0
        assert stats["tier_2_count"] > 0
        assert stats["tier_3_count"] > 0

    def test_tier_stats_returns_domain_lists(self):
        """Stats should return domain lists for each tier."""
        stats = get_tier_statistics()

        assert "tier_1_domains" in stats
        assert "reuters.com" in stats["tier_1_domains"]
