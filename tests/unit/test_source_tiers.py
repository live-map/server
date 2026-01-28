"""
Unit tests for Source Tier system (Phase 6 - Simplified 2-Tier).

Tests domain-based credibility tiers for LLM classifier pipeline.
Only Tier-1 (wire services) and Tier-2 (major outlets) are trusted.
"""

import pytest
from app.agent.source_tiers import (
    DomainTier,
    TIER_1_DOMAINS,
    TIER_2_DOMAINS,
    ALL_TRUSTED_DOMAINS,
    normalize_domain,
    get_domain_tier,
    get_domain_tier_info,
    get_min_sources_required,
    is_single_source_allowed,
    get_credibility_weight,
    evaluate_source_mix,
    get_tier_statistics,
    is_trusted_domain,
    is_tier1_domain,
    is_tier2_domain,
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
    """Tests for Tier-1 (wire services/government) classification."""

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

    def test_state_gov_is_tier1(self):
        """State.gov should be Tier-1."""
        assert get_domain_tier("state.gov") == DomainTier.TIER_1

    def test_tier1_single_source_allowed(self):
        """Tier-1 sources should allow single-source publishing."""
        assert is_single_source_allowed("reuters.com") is True
        assert is_single_source_allowed("apnews.com") is True

    def test_tier1_min_sources_is_1(self):
        """Tier-1 sources should require only 1 source."""
        assert get_min_sources_required("reuters.com") == 1
        assert get_min_sources_required("apnews.com") == 1

    def test_tier1_is_trusted(self):
        """Tier-1 sources should be trusted."""
        assert is_trusted_domain("reuters.com") is True
        assert is_tier1_domain("reuters.com") is True


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

    def test_latimes_is_tier2(self):
        """LA Times should be Tier-2."""
        assert get_domain_tier("latimes.com") == DomainTier.TIER_2

    def test_tier2_single_source_allowed(self):
        """Tier-2 sources should allow single-source publishing with verification."""
        assert is_single_source_allowed("bbc.com") is True
        assert is_single_source_allowed("nytimes.com") is True

    def test_tier2_min_sources_is_1(self):
        """Tier-2 sources should require only 1 source (with verification)."""
        assert get_min_sources_required("bbc.com") == 1

    def test_tier2_is_trusted(self):
        """Tier-2 sources should be trusted."""
        assert is_trusted_domain("bbc.com") is True
        assert is_tier2_domain("bbc.com") is True
        assert is_tier1_domain("bbc.com") is False


class TestUntrustedDomains:
    """Tests for UNTRUSTED (unknown/other) classification."""

    def test_unknown_domain_is_untrusted(self):
        """Unknown domain should be UNTRUSTED."""
        assert get_domain_tier("unknown-blog.com") == DomainTier.UNTRUSTED

    def test_untrusted_single_source_not_allowed(self):
        """UNTRUSTED sources should NOT allow single-source publishing."""
        assert is_single_source_allowed("random-blog.net") is False

    def test_untrusted_min_sources_is_2(self):
        """UNTRUSTED sources should require 2 sources."""
        assert get_min_sources_required("random-blog.net") == 2

    def test_untrusted_is_not_trusted(self):
        """UNTRUSTED sources should not be trusted."""
        assert is_trusted_domain("random-blog.net") is False
        assert is_tier1_domain("random-blog.net") is False
        assert is_tier2_domain("random-blog.net") is False


class TestCredibilityWeight:
    """Tests for credibility weight calculation."""

    def test_tier1_weight(self):
        """Tier-1 should have weight 0.95."""
        assert get_credibility_weight("reuters.com") == 0.95

    def test_tier2_weight(self):
        """Tier-2 should have weight 0.80."""
        assert get_credibility_weight("bbc.com") == 0.80

    def test_untrusted_weight(self):
        """UNTRUSTED should have weight 0.30."""
        assert get_credibility_weight("random-blog.net") == 0.30


class TestDomainTierInfo:
    """Tests for detailed domain tier info."""

    def test_tier_info_includes_domain(self):
        """Tier info should include normalized domain."""
        info = get_domain_tier_info("https://www.reuters.com/article")
        assert info["domain"] == "reuters.com"

    def test_tier_info_includes_tier(self):
        """Tier info should include tier classification."""
        info = get_domain_tier_info("reuters.com")
        assert info["tier"] == DomainTier.TIER_1.value

    def test_tier_info_includes_min_sources(self):
        """Tier info should include min sources required."""
        info = get_domain_tier_info("reuters.com")
        assert info["min_sources_required"] == 1

    def test_tier_info_tier2_needs_verification(self):
        """Tier-2 info should indicate LLM verification needed."""
        info = get_domain_tier_info("bbc.com")
        assert info["needs_llm_verification"] is True
        assert info["instant_publish"] is False

    def test_tier_info_tier1_instant_publish(self):
        """Tier-1 info should indicate instant publish allowed."""
        info = get_domain_tier_info("reuters.com")
        assert info["instant_publish"] is True
        assert info["needs_llm_verification"] is False


class TestEvaluateSourceMix:
    """Tests for source mix evaluation."""

    def test_tier1_single_source_immediate_publish(self):
        """Single Tier-1 source should allow immediate publishing."""
        sources = [{"url": "https://reuters.com/article/123"}]
        result = evaluate_source_mix(sources)

        assert result["has_tier1"] is True
        assert result["recommendation"] == "immediate_publish"

    def test_tier2_multiple_sources_publishable(self):
        """Multiple Tier-2 sources should be publishable."""
        sources = [
            {"url": "https://bbc.com/news/123"},
            {"url": "https://cnn.com/world/456"},
        ]
        result = evaluate_source_mix(sources)

        assert result["has_tier2"] is True
        assert result["recommendation"] == "publishable"

    def test_tier2_single_source_needs_verification(self):
        """Single Tier-2 source should need verification."""
        sources = [{"url": "https://bbc.com/news/123"}]
        result = evaluate_source_mix(sources)

        assert result["has_tier2"] is True
        assert result["recommendation"] == "needs_verification"

    def test_untrusted_single_source_do_not_publish(self):
        """Single UNTRUSTED source should not be published."""
        sources = [{"url": "https://random-blog.com/post/123"}]
        result = evaluate_source_mix(sources)

        assert result["has_tier1"] is False
        assert result["has_tier2"] is False
        assert result["recommendation"] == "do_not_publish"

    def test_empty_sources_no_sources(self):
        """Empty sources should return no_sources recommendation."""
        result = evaluate_source_mix([])

        assert result["recommendation"] == "no_sources"

    def test_tier_diversity_bonus(self):
        """Multiple tiers should give diversity bonus."""
        sources = [
            {"url": "https://reuters.com/article/123"},  # Tier-1
            {"url": "https://bbc.com/news/456"},  # Tier-2
        ]
        result = evaluate_source_mix(sources)

        assert result["tier_diversity_bonus"] > 0


class TestTierStatistics:
    """Tests for tier statistics."""

    def test_tier_stats_returns_counts(self):
        """Stats should return counts for each tier."""
        stats = get_tier_statistics()

        assert "tier_1_count" in stats
        assert "tier_2_count" in stats
        assert "total_trusted" in stats
        assert stats["tier_1_count"] > 0
        assert stats["tier_2_count"] > 0

    def test_tier_stats_returns_domain_lists(self):
        """Stats should return domain lists for each tier."""
        stats = get_tier_statistics()

        assert "tier_1_domains" in stats
        assert "tier_2_domains" in stats
        assert "reuters.com" in stats["tier_1_domains"]
        assert "bbc.com" in stats["tier_2_domains"]


class TestSubdomainHandling:
    """Tests for subdomain handling."""

    def test_subdomain_inherits_tier(self):
        """Subdomains should inherit parent domain tier."""
        assert get_domain_tier("news.reuters.com") == DomainTier.TIER_1
        assert get_domain_tier("world.bbc.com") == DomainTier.TIER_2

    def test_special_subdomains_normalized(self):
        """Special subdomains should be normalized."""
        assert is_tier2_domain("m.bbc.com") is True
        assert is_tier2_domain("edition.cnn.com") is True
