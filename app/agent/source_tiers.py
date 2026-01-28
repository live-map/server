"""
Source Tier Configuration - Trusted Domain Whitelist

NEW ARCHITECTURE (LLM Classifier):
- Tier-1: Instant publish (11 domains) - Wire services, international orgs, government
- Tier-2: LLM verification (48 domains) - Major news outlets worldwide
- Tier-3 and below: EXCLUDED from pipeline

Design Decision:
- Tier-3 sources (Reddit, local news, blogs) are completely removed
- This reduces volume by ~90% while maintaining quality
- Expected: ~20-50 articles per 15-minute scan
- LLM classifier handles categorization instead of pattern matching

Total: 59 trusted domains covering 90%+ of international news
"""

import logging
from enum import Enum
from typing import Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainTier(str, Enum):
    """
    Simplified domain credibility tiers for LLM classifier pipeline.

    Tier-1: Wire services, government - instant publish
    Tier-2: Major news outlets - LLM verification required
    UNTRUSTED: Not in whitelist - completely filtered out
    """
    TIER_1 = "tier_1"      # Instant publish - highest trust
    TIER_2 = "tier_2"      # LLM verification required
    UNTRUSTED = "untrusted"  # Not in whitelist - reject


# =============================================================================
# TIER-1: Instant Publish (11 domains)
# Wire services, international organizations, government sources
# =============================================================================

TIER_1_DOMAINS: Set[str] = {
    # Wire Services (4)
    "reuters.com",
    "apnews.com",
    "ap.org",
    "afp.com",

    # International Organizations (3)
    "un.org",
    "nato.int",
    "who.int",

    # Government Official Sources (4)
    "state.gov",
    "gov.uk",
    "europa.eu",
    "defense.gov",

    # Conflict Data (1)
    "acleddata.com",
}

# =============================================================================
# TIER-2: LLM Verification Required (48 domains)
# Major news outlets by region
# =============================================================================

TIER_2_DOMAINS: Set[str] = {
    # ---- United States (8) ----
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "cnn.com",
    "npr.org",
    "bloomberg.com",
    "politico.com",
    "axios.com",

    # ---- United Kingdom (7) ----
    "bbc.com",
    "bbc.co.uk",
    "theguardian.com",
    "ft.com",
    "telegraph.co.uk",
    "thetimes.co.uk",
    "independent.co.uk",

    # ---- Europe (6) ----
    "dw.com",
    "france24.com",
    "euronews.com",
    "spiegel.de",
    "lemonde.fr",
    "elpais.com",

    # ---- Middle East (5) ----
    "aljazeera.com",
    "haaretz.com",
    "timesofisrael.com",
    "jpost.com",
    "arabnews.com",

    # ---- Asia-Pacific (10) ----
    "scmp.com",
    "thehindu.com",
    "hindustantimes.com",
    "timesofindia.indiatimes.com",
    "japantimes.co.jp",
    "koreaherald.com",
    "straitstimes.com",
    "abc.net.au",
    "channelnewsasia.com",
    "yna.co.kr",

    # ---- Americas (4) ----
    "globalnews.ca",
    "cbc.ca",
    "eluniversal.com.mx",
    "latimes.com",

    # ---- Africa (3) ----
    "news24.com",
    "allafrica.com",
    "dailymaverick.co.za",

    # ---- Global/Financial (5) ----
    "cnbc.com",
    "economist.com",
    "foreignpolicy.com",
    "theatlantic.com",
    "newyorker.com",
}

# =============================================================================
# Combined Whitelist for Quick Lookup
# =============================================================================

ALL_TRUSTED_DOMAINS: Set[str] = TIER_1_DOMAINS | TIER_2_DOMAINS


def normalize_domain(url_or_domain: str) -> str:
    """
    Normalize a URL or domain to its base domain.

    Examples:
        "https://www.reuters.com/world/article" -> "reuters.com"
        "bbc.co.uk" -> "bbc.co.uk"
        "news.bbc.co.uk" -> "bbc.co.uk"
    """
    # If it looks like a URL, parse it
    if url_or_domain.startswith(("http://", "https://", "//")):
        try:
            parsed = urlparse(url_or_domain)
            domain = parsed.netloc.lower()
        except Exception:
            domain = url_or_domain.lower()
    else:
        domain = url_or_domain.lower()

    # Remove www prefix
    if domain.startswith("www."):
        domain = domain[4:]

    # Remove common subdomains
    for prefix in ["news.", "m.", "mobile.", "edition.", "amp.", "edition."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            break

    return domain


def get_domain_tier(url_or_domain: str) -> DomainTier:
    """
    Get the tier for a domain.

    Args:
        url_or_domain: Domain or URL to check (e.g., "reuters.com", "https://www.bbc.com/news")

    Returns:
        DomainTier enum value
    """
    domain = normalize_domain(url_or_domain)

    # Check Tier-1 first
    if domain in TIER_1_DOMAINS:
        return DomainTier.TIER_1

    # Check Tier-2
    if domain in TIER_2_DOMAINS:
        return DomainTier.TIER_2

    # Check if domain ends with any trusted domain (for subdomains)
    for trusted in TIER_1_DOMAINS:
        if domain.endswith(f".{trusted}"):
            return DomainTier.TIER_1

    for trusted in TIER_2_DOMAINS:
        if domain.endswith(f".{trusted}"):
            return DomainTier.TIER_2

    return DomainTier.UNTRUSTED


def is_trusted_domain(domain: str) -> bool:
    """
    Check if a domain is in the trusted whitelist (Tier-1 or Tier-2).

    Args:
        domain: Domain to check

    Returns:
        True if domain is Tier-1 or Tier-2
    """
    return get_domain_tier(domain) != DomainTier.UNTRUSTED


def is_tier1_domain(domain: str) -> bool:
    """Check if domain is Tier-1 (wire service/government)."""
    return get_domain_tier(domain) == DomainTier.TIER_1


def is_tier2_domain(domain: str) -> bool:
    """Check if domain is Tier-2 (major news outlet)."""
    return get_domain_tier(domain) == DomainTier.TIER_2


def get_trusted_domain_list() -> list[str]:
    """
    Get list of all trusted domains for API filtering.

    Returns:
        List of all 59 trusted domains (sorted)
    """
    return sorted(ALL_TRUSTED_DOMAINS)


def filter_by_trusted_domains(
    articles: list[dict],
    domain_key: str = "domain",
) -> tuple[list[dict], int]:
    """
    Filter articles to only include those from trusted domains.

    Args:
        articles: List of article dicts
        domain_key: Key in dict containing domain (default: "domain")

    Returns:
        Tuple of (filtered articles, rejected count)
    """
    filtered = []
    rejected_count = 0

    for article in articles:
        domain = article.get(domain_key, "")
        tier = get_domain_tier(domain)

        if tier != DomainTier.UNTRUSTED:
            # Add tier info to article
            article["_source_tier"] = tier.value
            article["_is_tier1"] = (tier == DomainTier.TIER_1)
            filtered.append(article)
        else:
            rejected_count += 1
            logger.debug(f"[DOMAIN-FILTER] Rejected untrusted domain: {domain}")

    if rejected_count > 0:
        logger.info(
            f"[DOMAIN-FILTER] {len(filtered)}/{len(articles)} articles from trusted domains "
            f"({rejected_count} rejected)"
        )

    return filtered, rejected_count


def check_domain_whitelist(domain: str) -> dict:
    """
    Get detailed information about a domain's whitelist status.

    Args:
        domain: Domain to check

    Returns:
        Dict with tier info and whether LLM verification is needed
    """
    tier = get_domain_tier(domain)
    normalized = normalize_domain(domain)

    return {
        "domain": normalized,
        "tier": tier.value,
        "is_trusted": tier != DomainTier.UNTRUSTED,
        "is_tier1": tier == DomainTier.TIER_1,
        "is_tier2": tier == DomainTier.TIER_2,
        "needs_llm_verification": tier == DomainTier.TIER_2,
        "instant_publish": tier == DomainTier.TIER_1,
    }


# =============================================================================
# Statistics
# =============================================================================

def get_tier_statistics() -> dict:
    """Get statistics about configured tiers."""
    return {
        "tier_1_count": len(TIER_1_DOMAINS),
        "tier_2_count": len(TIER_2_DOMAINS),
        "total_trusted": len(ALL_TRUSTED_DOMAINS),
        "tier_1_domains": sorted(TIER_1_DOMAINS),
        "tier_2_domains": sorted(TIER_2_DOMAINS),
    }


# Constants for external use
TIER_1_COUNT = len(TIER_1_DOMAINS)
TIER_2_COUNT = len(TIER_2_DOMAINS)
TOTAL_TRUSTED_COUNT = len(ALL_TRUSTED_DOMAINS)


# =============================================================================
# Credibility Weighting
# =============================================================================

# Credibility weights by tier
TIER_CREDIBILITY_WEIGHTS = {
    DomainTier.TIER_1: 0.95,      # Wire services, government - highest trust
    DomainTier.TIER_2: 0.80,      # Major news outlets
    DomainTier.UNTRUSTED: 0.30,   # Unknown sources
}


def is_single_source_allowed(domain: str) -> bool:
    """
    Check if a single source is sufficient for publishing.

    Tier-1 and Tier-2 sources allow single-source publishing.
    UNTRUSTED sources require multiple sources.

    Args:
        domain: Domain to check

    Returns:
        True if single-source publishing is allowed
    """
    tier = get_domain_tier(domain)
    return tier in {DomainTier.TIER_1, DomainTier.TIER_2}


def get_min_sources_required(domain: str) -> int:
    """
    Get minimum number of sources required for publishing.

    Args:
        domain: Domain to check

    Returns:
        Minimum sources required (1 for trusted, 2+ for untrusted)
    """
    tier = get_domain_tier(domain)
    if tier == DomainTier.TIER_1:
        return 1
    elif tier == DomainTier.TIER_2:
        return 1  # With LLM verification
    else:
        return 2  # UNTRUSTED requires multiple sources


def get_domain_tier_info(domain: str) -> dict:
    """
    Get detailed tier information for a domain.

    Args:
        domain: Domain to check

    Returns:
        Dict with tier, credibility, and publishing requirements
    """
    tier = get_domain_tier(domain)
    normalized = normalize_domain(domain)

    return {
        "domain": normalized,
        "tier": tier.value,
        "tier_name": tier.name,
        "is_trusted": tier != DomainTier.UNTRUSTED,
        "single_source_allowed": tier in {DomainTier.TIER_1, DomainTier.TIER_2},
        "min_sources_required": get_min_sources_required(domain),
        "credibility_weight": TIER_CREDIBILITY_WEIGHTS.get(tier, 0.30),
        "needs_llm_verification": tier == DomainTier.TIER_2,
        "instant_publish": tier == DomainTier.TIER_1,
    }


def get_credibility_weight(domain_or_tier: str | DomainTier) -> float:
    """
    Get credibility weight for a domain or tier.

    Args:
        domain_or_tier: Domain string or DomainTier enum

    Returns:
        Credibility weight (0.0 - 1.0)
    """
    if isinstance(domain_or_tier, DomainTier):
        tier = domain_or_tier
    else:
        tier = get_domain_tier(domain_or_tier)

    return TIER_CREDIBILITY_WEIGHTS.get(tier, 0.30)


def evaluate_source_mix(sources: list[dict]) -> dict:
    """
    Evaluate the mix of sources for confidence scoring.

    Args:
        sources: List of source dicts with 'domain' or 'url' keys

    Returns:
        Dict with evaluation results:
        - tier_counts: Count of sources by tier
        - has_tier1: Whether any Tier-1 source exists
        - has_tier2: Whether any Tier-2 source exists
        - average_credibility: Average credibility weight
        - tier_diversity_bonus: Bonus for having multiple tiers
        - recommendation: publish recommendation
    """
    if not sources:
        return {
            "tier_counts": {},
            "has_tier1": False,
            "has_tier2": False,
            "average_credibility": 0.0,
            "tier_diversity_bonus": 0.0,
            "recommendation": "no_sources",
        }

    tier_counts = {
        DomainTier.TIER_1: 0,
        DomainTier.TIER_2: 0,
        DomainTier.UNTRUSTED: 0,
    }
    credibility_sum = 0.0

    for source in sources:
        domain = source.get("domain") or source.get("url", "")
        tier = get_domain_tier(domain)
        tier_counts[tier] += 1
        credibility_sum += get_credibility_weight(tier)

    average_credibility = credibility_sum / len(sources) if sources else 0.0

    # Calculate tier diversity bonus
    tiers_present = sum(1 for count in tier_counts.values() if count > 0)
    tier_diversity_bonus = 0.05 * (tiers_present - 1) if tiers_present > 1 else 0.0

    # Determine recommendation
    has_tier1 = tier_counts[DomainTier.TIER_1] > 0
    has_tier2 = tier_counts[DomainTier.TIER_2] > 0

    if has_tier1:
        recommendation = "immediate_publish"
    elif has_tier2 and len(sources) >= 2:
        recommendation = "publishable"
    elif has_tier2:
        recommendation = "needs_verification"
    else:
        recommendation = "do_not_publish"

    return {
        "tier_counts": {k.value: v for k, v in tier_counts.items()},
        "has_tier1": has_tier1,
        "has_tier2": has_tier2,
        "average_credibility": round(average_credibility, 3),
        "tier_diversity_bonus": round(tier_diversity_bonus, 3),
        "recommendation": recommendation,
    }


# =============================================================================
# Backward Compatibility (deprecated - remove after migration)
# =============================================================================

# Old enum values for compatibility
class SourceTier(str, Enum):
    """Deprecated: Use DomainTier instead"""
    TIER1_GOVT = "tier1_govt"
    TIER2_NEWS = "tier2_news"
    TIER3_SOCIAL = "tier3_social"


# Map old tier names to new
SOURCE_TIER_MAP = {
    SourceTier.TIER1_GOVT: DomainTier.TIER_1,
    SourceTier.TIER2_NEWS: DomainTier.TIER_2,
    SourceTier.TIER3_SOCIAL: DomainTier.UNTRUSTED,
}
