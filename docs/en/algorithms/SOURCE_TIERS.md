# Source Tiers Algorithm

## Overview

The Source Tier system classifies news domains into four credibility levels, determining verification requirements and publication eligibility. This enables faster publication for trusted sources while maintaining quality for less-established ones.

---

## Domain Tier Classifications

### Tier-1: Wire Services (0.95 credibility)

Primary news sources with rigorous editorial standards.

| Domain | Type |
|--------|------|
| reuters.com | Wire service |
| apnews.com | Wire service |
| afp.com | Wire service |
| un.org | International organization |
| nato.int | International organization |
| who.int | International organization |
| state.gov | Government |
| gov.uk | Government |
| europa.eu | Government |
| acleddata.com | Research data |

**Characteristics:**
- Single-source publishing allowed
- No verification delay
- Minimum sources required: 1
- Breaking news fast-path eligible

### Tier-2: Major News Outlets (0.85 credibility)

Established news organizations with professional journalism standards.

| Domain | Region |
|--------|--------|
| nytimes.com | US |
| washingtonpost.com | US |
| wsj.com | US |
| cnn.com | US |
| nbcnews.com | US |
| bbc.com | UK |
| theguardian.com | UK |
| telegraph.co.uk | UK |
| ft.com | UK |
| dw.com | Germany |
| france24.com | France |
| aljazeera.com | Middle East |
| scmp.com | Asia |
| japantimes.co.jp | Asia |
| thehindu.com | Asia |

**Characteristics:**
- Single-source publishing allowed
- 60-minute verification delay
- Minimum sources required: 1
- Breaking news fast-path eligible

### Tier-3: Regional/Specialty (0.70 credibility)

Regional newspapers and specialty publications.

| Domain | Type |
|--------|------|
| latimes.com | Regional US |
| chicagotribune.com | Regional US |
| bostonglobe.com | Regional US |
| manchestereveningnews.co.uk | Regional UK |
| irishtimes.com | Regional Europe |
| defensenews.com | Specialty |
| aviationweek.com | Specialty |
| nature.com | Academic |
| sciencemag.org | Academic |

**Characteristics:**
- Two-Source Rule required
- No verification delay
- Minimum sources required: 2
- Standard gate processing

### Tier-4: Other (0.50 credibility)

Blogs, aggregators, and unclassified sources.

**Characteristics:**
- Three+ sources required
- Higher verification burden
- Minimum sources required: 3
- Full gate processing
- Default tier for unknown domains

---

## Publication Rules

### Decision Matrix

| Tier | Min Sources | Single Source OK | Verification Delay | Breaking Fast-Path |
|------|-------------|------------------|-------------------|-------------------|
| Tier-1 | 1 | Yes | 0 min | Yes |
| Tier-2 | 1 | Yes | 60 min | Yes |
| Tier-3 | 2 | No | 0 min | No |
| Tier-4 | 3 | No | 0 min | No |

### Publication Actions

```python
def evaluate_source_mix(sources: list[dict]) -> dict:
    """
    Returns recommended publication action based on source mix.
    """
    tiers = [get_domain_tier(s["url"]) for s in sources]
    highest_tier = min(tiers)  # Tier-1 is "highest" quality

    if DomainTier.TIER_1 in tiers:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_IMMEDIATE",
            "verification_required": False,
            "verification_delay_minutes": 0,
        }
    elif DomainTier.TIER_2 in tiers:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_WITH_VERIFICATION",
            "verification_required": True,
            "verification_delay_minutes": 60,
        }
    elif len(set(get_domain(s["url"]) for s in sources)) >= 2:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_STANDARD",
            "verification_required": False,
            "verification_delay_minutes": 0,
        }
    else:
        return {
            "can_publish": False,
            "recommended_action": "NEED_MORE_SOURCES",
            "verification_required": True,
            "verification_delay_minutes": 0,
        }
```

---

## Domain Classification

### Domain Normalization

URLs are normalized before tier lookup:

```python
def normalize_domain(url_or_domain: str) -> str:
    """
    Normalize domain by removing common prefixes.

    Examples:
        "https://www.reuters.com/world/article" → "reuters.com"
        "news.bbc.com" → "bbc.com"
        "m.cnn.com" → "cnn.com"
    """
    # Extract domain from URL
    if "://" in url_or_domain:
        domain = urlparse(url_or_domain).netloc
    else:
        domain = url_or_domain

    # Remove prefixes
    prefixes = ["www.", "news.", "m.", "mobile.", "edition.", "amp."]
    for prefix in prefixes:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]

    return domain.lower()
```

### Tier Lookup

```python
def get_domain_tier(url_or_domain: str) -> DomainTier:
    domain = normalize_domain(url_or_domain)

    # Check each tier
    for tier1_domain in TIER_1_DOMAINS:
        if tier1_domain in domain:
            return DomainTier.TIER_1

    for tier2_domain in TIER_2_DOMAINS:
        if tier2_domain in domain:
            return DomainTier.TIER_2

    for tier3_domain in TIER_3_DOMAINS:
        if tier3_domain in domain:
            return DomainTier.TIER_3

    return DomainTier.TIER_4  # Default
```

---

## Credibility Weight

Each tier has an associated credibility weight used in confidence scoring:

```python
def get_credibility_weight(url_or_domain: str) -> float:
    tier = get_domain_tier(url_or_domain)
    return {
        DomainTier.TIER_1: 0.95,
        DomainTier.TIER_2: 0.85,
        DomainTier.TIER_3: 0.70,
        DomainTier.TIER_4: 0.50,
    }[tier]
```

---

## Two-Source Rule Integration

The Two-Source Rule from journalism is satisfied when:

1. **Single Tier-1 source** (wire service or government)
2. **Single Tier-2 source** (with 60-min verification)
3. **Two+ sources from different domains** (standard rule)

```python
def check_two_source_rule(
    sources: list[dict],
    domain_tier_eval: dict | None = None,
) -> bool:
    # Single Tier-1 government source is sufficient
    if len(sources) == 1:
        tier = get_domain_tier(sources[0]["url"])
        if tier == DomainTier.TIER_1:
            return True

    # Domain tier allows single-source publishing
    if domain_tier_eval and domain_tier_eval.get("can_publish"):
        action = domain_tier_eval.get("recommended_action", "")
        if action in ("PUBLISH_IMMEDIATE", "PUBLISH_WITH_VERIFICATION"):
            return True

    # Standard Two-Source Rule
    if len(sources) < 2:
        return False

    unique_domains = set(normalize_domain(s["url"]) for s in sources)
    return len(unique_domains) >= 2
```

---

## Breaking News Integration

Tier-1 and Tier-2 sources are eligible for the breaking news fast-path:

```python
def is_fast_path_eligible(source_url: str) -> bool:
    tier = get_domain_tier(source_url)
    return tier in [DomainTier.TIER_1, DomainTier.TIER_2]
```

When breaking news is detected from fast-path eligible sources:
- **High confidence (≥0.8)**: Skip Gate 0, Gate 2, Gate 3
- **Standard confidence (0.6-0.79)**: Skip Gate 2, Gate 3

---

## Example Evaluations

### Example 1: Reuters Exclusive

**Input:** Single source from reuters.com

**Evaluation:**
```
Domain: reuters.com
Tier: TIER_1
Credibility: 0.95
Single source allowed: Yes
Verification delay: 0 min
Action: PUBLISH_IMMEDIATE
```

### Example 2: BBC + CNN

**Input:** Two sources from bbc.com and cnn.com

**Evaluation:**
```
Domains: bbc.com, cnn.com
Tiers: TIER_2, TIER_2
Avg credibility: 0.85
Unique domains: 2
Action: PUBLISH_WITH_VERIFICATION (60 min)
```

### Example 3: Local News Only

**Input:** Single source from localgazette.com

**Evaluation:**
```
Domain: localgazette.com
Tier: TIER_4
Credibility: 0.50
Single source allowed: No
Action: NEED_MORE_SOURCES
```

---

## Domain Lists

### Complete Tier-1 List (19 domains)

```python
TIER_1_DOMAINS = {
    # Wire services
    "apnews.com", "reuters.com", "afp.com",
    # International organizations
    "un.org", "nato.int", "who.int", "imf.org", "worldbank.org",
    # Government
    "state.gov", "gov.uk", "europa.eu", "defense.gov",
    # Research
    "acleddata.com",
}
```

### Complete Tier-2 List (59 domains)

```python
TIER_2_DOMAINS = {
    # US outlets
    "nytimes.com", "washingtonpost.com", "wsj.com", "cnn.com",
    "nbcnews.com", "abcnews.go.com", "cbsnews.com", "foxnews.com",
    "npr.org", "pbs.org", "politico.com", "theatlantic.com",
    # UK outlets
    "bbc.com", "bbc.co.uk", "theguardian.com", "telegraph.co.uk",
    "ft.com", "independent.co.uk", "thetimes.co.uk", "economist.com",
    "sky.com",
    # European outlets
    "dw.com", "france24.com", "lemonde.fr", "spiegel.de",
    "rfi.fr", "euronews.com",
    # Asia-Pacific
    "aljazeera.com", "scmp.com", "japantimes.co.jp", "thehindu.com",
    "smh.com.au", "abc.net.au", "channelnewsasia.com",
    # Middle East
    "haaretz.com", "timesofisrael.com", "jpost.com",
}
```

### Complete Tier-3 List (37 domains)

```python
TIER_3_DOMAINS = {
    # Regional US
    "latimes.com", "chicagotribune.com", "bostonglobe.com",
    "sfchronicle.com", "seattletimes.com", "denverpost.com",
    # Regional international
    "manchestereveningnews.co.uk", "irishtimes.com", "rte.ie",
    "theaustralian.com.au",
    # Specialty
    "defensenews.com", "aviationweek.com", "janes.com",
    "militarytimes.com", "defenseone.com",
    # Academic/Science
    "nature.com", "sciencemag.org", "newscientist.com",
}
```

---

## Configuration

```python
# Tier weights
DOMAIN_TIER_WEIGHTS = {
    DomainTier.TIER_1: 0.95,
    DomainTier.TIER_2: 0.85,
    DomainTier.TIER_3: 0.70,
    DomainTier.TIER_4: 0.50,
}

# Minimum sources per tier
MIN_SOURCES_BY_TIER = {
    DomainTier.TIER_1: 1,
    DomainTier.TIER_2: 1,
    DomainTier.TIER_3: 2,
    DomainTier.TIER_4: 3,
}

# Verification delays
VERIFICATION_DELAY_MINUTES = {
    DomainTier.TIER_1: 0,
    DomainTier.TIER_2: 60,
    DomainTier.TIER_3: 0,
    DomainTier.TIER_4: 0,
}
```

---

## File Location

```
app/agent/source_tiers.py
```

---

## Related Documentation

- [ADR-011: Domain Tiers](../adr/ADR-011-domain-tiers.md)
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md) (Trigger tiers)
- [Confidence Scoring](CONFIDENCE_SCORING.md)
- [ADR-007: Breaking News](../adr/ADR-007-breaking-news.md)
