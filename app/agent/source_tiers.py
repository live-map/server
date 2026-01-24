"""
Source Tier System for Domain-Based Credibility

Implements a tiered credibility system based on news source domains.
This allows single-source publishing for highly credible wire services
while maintaining the Two-Source Rule for less established sources.

Research basis:
- Wikipedia RS Policy (Reliable Sources)
- Reuters Tracer methodology
- AP, AFP fact-checking standards
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainTier(str, Enum):
    """
    Domain credibility tiers based on journalism standards.

    Tier-1 (Wire Services): Can publish with single source
        - Major wire services with multi-source verification as policy
        - AP, Reuters, AFP have internal fact-checking before publication

    Tier-2 (Major Outlets): Publish with delayed verification
        - Major international news organizations
        - High editorial standards but may break stories unverified

    Tier-3 (Regional/Specialty): Requires 2 sources
        - Regional news, specialty outlets
        - Good credibility but limited resources

    Tier-4 (Aggregators/Blogs): Requires 3+ sources
        - News aggregators, blogs, lesser-known sites
        - Higher verification burden required
    """
    TIER_1 = "tier_1_wire"      # Wire services (single-source OK)
    TIER_2 = "tier_2_major"     # Major news outlets (1hr verification)
    TIER_3 = "tier_3_regional"  # Regional/specialty news (2 sources)
    TIER_4 = "tier_4_other"     # Aggregators/blogs (3+ sources)


# Wire services - highest credibility, can publish single-source
# These organizations have rigorous internal verification processes
TIER_1_DOMAINS: set[str] = {
    # Major Wire Services
    "apnews.com",
    "ap.org",
    "reuters.com",
    "afp.com",

    # Government/Official Sources (treated as wire-equivalent)
    "state.gov",
    "gov.uk",
    "europa.eu",
    "un.org",
    "nato.int",
    "who.int",

    # Major Research/Data Sources
    "acleddata.com",
}

# Major international news outlets - high credibility
# Publish immediately but schedule verification within 1 hour
TIER_2_DOMAINS: set[str] = {
    # US Major Outlets
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "cnn.com",
    "nbcnews.com",
    "abcnews.go.com",
    "cbsnews.com",
    "npr.org",
    "usatoday.com",
    "bloomberg.com",
    "politico.com",

    # UK Major Outlets
    "bbc.com",
    "bbc.co.uk",
    "theguardian.com",
    "telegraph.co.uk",
    "ft.com",
    "thetimes.co.uk",
    "independent.co.uk",
    "sky.com",

    # European Major Outlets
    "dw.com",
    "france24.com",
    "euronews.com",
    "lemonde.fr",
    "spiegel.de",
    "elpais.com",
    "corriere.it",

    # Middle East & Asia
    "aljazeera.com",
    "aljazeera.net",
    "haaretz.com",
    "timesofisrael.com",
    "jpost.com",
    "scmp.com",
    "japantimes.co.jp",
    "koreaherald.com",
    "straitstimes.com",
    "thehindu.com",
    "hindustantimes.com",

    # Australia & Others
    "abc.net.au",
    "smh.com.au",
    "theaustralian.com.au",
    "globalnews.ca",
    "cbc.ca",

    # Specialty/Quality Sources
    "foreignpolicy.com",
    "theatlantic.com",
    "economist.com",
    "newyorker.com",
}

# Regional and specialty news - moderate credibility
TIER_3_DOMAINS: set[str] = {
    # Regional US
    "latimes.com",
    "chicagotribune.com",
    "bostonglobe.com",
    "sfgate.com",
    "dallasnews.com",
    "denverpost.com",
    "seattletimes.com",
    "miamiherald.com",

    # Regional UK/Europe
    "manchestereveningnews.co.uk",
    "birminghammail.co.uk",
    "edinburghnews.scotsman.com",
    "irishtimes.com",
    "rte.ie",

    # Regional Asia
    "channelnewsasia.com",
    "asiaone.com",
    "bangkokpost.com",
    "todayonline.com",
    "inquirer.net",

    # Specialty Sources
    "defenseone.com",
    "defensenews.com",
    "militarytimes.com",
    "aviationweek.com",
    "spacenews.com",
    "livescience.com",
    "sciencemag.org",
    "nature.com",
}


@dataclass
class DomainTierInfo:
    """Information about a domain's tier classification"""
    domain: str
    tier: DomainTier
    min_sources_required: int
    single_source_allowed: bool
    verification_delay_minutes: int
    credibility_weight: float
    notes: str = ""


# Tier configuration
TIER_CONFIG: dict[DomainTier, dict] = {
    DomainTier.TIER_1: {
        "min_sources": 1,
        "single_source_allowed": True,
        "verification_delay_minutes": 0,  # Publish immediately
        "credibility_weight": 0.95,
    },
    DomainTier.TIER_2: {
        "min_sources": 1,
        "single_source_allowed": True,
        "verification_delay_minutes": 60,  # Verify within 1 hour
        "credibility_weight": 0.85,
    },
    DomainTier.TIER_3: {
        "min_sources": 2,
        "single_source_allowed": False,
        "verification_delay_minutes": 0,  # Standard Two-Source Rule
        "credibility_weight": 0.70,
    },
    DomainTier.TIER_4: {
        "min_sources": 3,
        "single_source_allowed": False,
        "verification_delay_minutes": 0,  # Higher verification burden
        "credibility_weight": 0.50,
    },
}


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

    # Remove news/m/mobile subdomains
    for prefix in ["news.", "m.", "mobile.", "edition.", "amp."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            break

    return domain


def get_domain_tier(url_or_domain: str) -> DomainTier:
    """
    Get the credibility tier for a domain.

    Args:
        url_or_domain: URL or domain string

    Returns:
        DomainTier classification
    """
    domain = normalize_domain(url_or_domain)

    # Check each tier
    if domain in TIER_1_DOMAINS:
        return DomainTier.TIER_1
    elif domain in TIER_2_DOMAINS:
        return DomainTier.TIER_2
    elif domain in TIER_3_DOMAINS:
        return DomainTier.TIER_3
    else:
        return DomainTier.TIER_4


def get_domain_tier_info(url_or_domain: str) -> DomainTierInfo:
    """
    Get detailed tier information for a domain.

    Args:
        url_or_domain: URL or domain string

    Returns:
        DomainTierInfo with all tier details
    """
    domain = normalize_domain(url_or_domain)
    tier = get_domain_tier(domain)
    config = TIER_CONFIG[tier]

    return DomainTierInfo(
        domain=domain,
        tier=tier,
        min_sources_required=config["min_sources"],
        single_source_allowed=config["single_source_allowed"],
        verification_delay_minutes=config["verification_delay_minutes"],
        credibility_weight=config["credibility_weight"],
    )


def get_min_sources_required(url_or_domain: str) -> int:
    """
    Get minimum number of sources required for publication.

    This is the key function for implementing tiered Two-Source Rule.

    Args:
        url_or_domain: URL or domain string

    Returns:
        Minimum number of sources required (1-3)
    """
    tier = get_domain_tier(url_or_domain)
    return TIER_CONFIG[tier]["min_sources"]


def is_single_source_allowed(url_or_domain: str) -> bool:
    """
    Check if single-source publishing is allowed for this domain.

    Args:
        url_or_domain: URL or domain string

    Returns:
        True if single-source publishing is allowed
    """
    tier = get_domain_tier(url_or_domain)
    return TIER_CONFIG[tier]["single_source_allowed"]


def get_credibility_weight(url_or_domain: str) -> float:
    """
    Get credibility weight for confidence scoring.

    Args:
        url_or_domain: URL or domain string

    Returns:
        Credibility weight (0.0-1.0)
    """
    tier = get_domain_tier(url_or_domain)
    return TIER_CONFIG[tier]["credibility_weight"]


def evaluate_source_mix(sources: list[dict]) -> dict:
    """
    Evaluate a mix of sources for publication eligibility.

    Args:
        sources: List of source dicts with 'url' or 'domain' keys

    Returns:
        dict with evaluation results:
        - can_publish: bool
        - reason: str
        - highest_tier: DomainTier
        - tier_breakdown: dict[DomainTier, int]
        - recommended_action: str
        - verification_required: bool
        - verification_delay_minutes: int
    """
    if not sources:
        return {
            "can_publish": False,
            "reason": "No sources provided",
            "highest_tier": None,
            "tier_breakdown": {},
            "recommended_action": "REJECT",
            "verification_required": False,
            "verification_delay_minutes": 0,
        }

    # Categorize sources by tier
    tier_breakdown: dict[DomainTier, list[str]] = {
        DomainTier.TIER_1: [],
        DomainTier.TIER_2: [],
        DomainTier.TIER_3: [],
        DomainTier.TIER_4: [],
    }

    for source in sources:
        url = source.get("url", source.get("domain", ""))
        if url:
            domain = normalize_domain(url)
            tier = get_domain_tier(url)
            tier_breakdown[tier].append(domain)

    # Determine highest tier
    highest_tier = DomainTier.TIER_4
    for tier in [DomainTier.TIER_1, DomainTier.TIER_2, DomainTier.TIER_3, DomainTier.TIER_4]:
        if tier_breakdown[tier]:
            highest_tier = tier
            break

    # Count total unique sources
    total_sources = sum(len(domains) for domains in tier_breakdown.values())
    unique_domains = set()
    for domains in tier_breakdown.values():
        unique_domains.update(domains)

    # Evaluate based on highest tier
    can_publish = False
    reason = ""
    recommended_action = "REJECT"
    verification_required = False
    verification_delay_minutes = 0

    if tier_breakdown[DomainTier.TIER_1]:
        # Tier-1 source present - can publish single-source
        can_publish = True
        reason = f"Tier-1 wire service source: {tier_breakdown[DomainTier.TIER_1][0]}"
        recommended_action = "PUBLISH_IMMEDIATE"
        logger.info(f"[SOURCE-TIER] Single-source publish allowed: {reason}")

    elif tier_breakdown[DomainTier.TIER_2]:
        # Tier-2 source present - publish with verification schedule
        can_publish = True
        reason = f"Tier-2 major outlet: {tier_breakdown[DomainTier.TIER_2][0]}"
        recommended_action = "PUBLISH_WITH_VERIFICATION"
        verification_required = True
        verification_delay_minutes = 60
        logger.info(f"[SOURCE-TIER] Publish with 1hr verification: {reason}")

    elif len(unique_domains) >= 2:
        # 2+ unique domains from Tier-3/4 - standard Two-Source Rule
        can_publish = True
        reason = f"Two-Source Rule satisfied: {len(unique_domains)} unique domains"
        recommended_action = "PUBLISH_STANDARD"
        logger.info(f"[SOURCE-TIER] Two-Source Rule satisfied: {unique_domains}")

    else:
        # Single Tier-3/4 source - reject
        can_publish = False
        reason = f"Single Tier-{highest_tier.value.split('_')[1]} source requires additional verification"
        recommended_action = "NEED_MORE_SOURCES"
        logger.warning(f"[SOURCE-TIER] Rejected: {reason}")

    return {
        "can_publish": can_publish,
        "reason": reason,
        "highest_tier": highest_tier,
        "tier_breakdown": {k.value: v for k, v in tier_breakdown.items()},
        "recommended_action": recommended_action,
        "verification_required": verification_required,
        "verification_delay_minutes": verification_delay_minutes,
        "unique_domain_count": len(unique_domains),
    }


def get_tier_statistics() -> dict:
    """Get statistics about configured tiers."""
    return {
        "tier_1_count": len(TIER_1_DOMAINS),
        "tier_2_count": len(TIER_2_DOMAINS),
        "tier_3_count": len(TIER_3_DOMAINS),
        "tier_1_domains": sorted(TIER_1_DOMAINS),
        "tier_2_domains": sorted(TIER_2_DOMAINS),
        "tier_3_domains": sorted(TIER_3_DOMAINS),
    }
