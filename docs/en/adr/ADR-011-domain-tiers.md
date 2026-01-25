# ADR-011: Domain-Based Tier System

## Status
Accepted

## Context

The existing tier system (ADR-003) classifies **trigger sources** (GDELT, USGS, Reddit) but not individual **domains** within those sources. This created issues:

1. GDELT aggregates from thousands of publishers with varying credibility
2. A Reuters article via GDELT should be treated differently than a blog
3. The Two-Source Rule couldn't account for source quality
4. Breaking news from wire services was delayed unnecessarily

We needed a way to classify individual domains (reuters.com, bbc.com, localblog.com) independently of their trigger source.

## Decision

Implement a 4-tier domain classification system complementing the existing trigger tier system.

### Domain Tier Structure

| Tier | Credibility | Min Sources | Single Source | Fast-Path |
|------|-------------|-------------|---------------|-----------|
| **Tier-1** | 0.95 | 1 | Yes | Yes |
| **Tier-2** | 0.85 | 1 | Yes (60m verify) | Yes |
| **Tier-3** | 0.70 | 2 | No | No |
| **Tier-4** | 0.50 | 3 | No | No |

### Tier Definitions

**Tier-1: Wire Services & Official Sources**
- Wire: Reuters, AP, AFP
- Government: UN, NATO, WHO, State Dept
- Rationale: Professional editorial standards, original reporting

**Tier-2: Major News Outlets**
- US: NYT, Washington Post, CNN, NPR
- UK: BBC, Guardian, Telegraph, FT
- Europe: DW, France24, Le Monde
- Asia: Al Jazeera, SCMP, Japan Times
- Rationale: Established newsrooms, fact-checking processes

**Tier-3: Regional/Specialty**
- Regional: LA Times, Chicago Tribune, Irish Times
- Specialty: Defense News, Nature, Science
- Rationale: Credible but narrower scope

**Tier-4: Other**
- Default for unlisted domains
- Blogs, aggregators, unknown sources
- Rationale: Unverified editorial standards

### Two-Source Rule Enhancement

The Two-Source Rule is now satisfied by:
1. Single Tier-1 domain source (immediate publish)
2. Single Tier-2 domain source (with 60-minute verification)
3. Two+ sources from different domains (standard rule)

### Integration with Trigger Tiers

| Source | Trigger Tier | Domain Tier | Used |
|--------|--------------|-------------|------|
| Reuters via GDELT | Tier-1 News (0.90) | Tier-1 Domain (0.95) | Higher: 0.95 |
| Blog via GDELT | Tier-1 News (0.90) | Tier-4 Domain (0.50) | Average or domain |
| USGS direct | Tier-1 Govt (0.99) | N/A | Trigger: 0.99 |

## Consequences

### Positive
- Wire service articles published immediately
- Quality differentiation within aggregators
- Breaking news fast-path enabled
- More accurate confidence scoring
- Maintains Two-Source Rule integrity

### Negative
- Maintenance burden for domain lists
- May miss new credible outlets
- Subjectivity in tier assignment
- Two tier systems to manage
- Potential for gaming/spoofing

## Alternatives Considered

### Alternative A: Per-Domain Reputation Scores
Assign individual scores (0.0-1.0) to each domain.

**Rejected because:**
- Thousands of domains to track
- Difficult to assign/maintain scores
- Overly complex
- No clear methodology

### Alternative B: External Reputation API
Use third-party reputation services (NewsGuard, etc.).

**Rejected because:**
- External dependency
- Cost per lookup
- May not cover all domains
- Different criteria than ours

### Alternative C: ML-Based Classification
Train model to classify domain credibility.

**Rejected because:**
- Black-box decisions
- Requires training data
- May learn biases
- Difficult to audit/explain

### Alternative D: Merge with Trigger Tiers
Combine domain and trigger tiers into one system.

**Rejected because:**
- Different purposes (source vs domain)
- Trigger tiers for data sources
- Domain tiers for content credibility
- Would oversimplify

## Implementation

```python
# Domain tier lookup
def get_domain_tier(url_or_domain: str) -> DomainTier:
    domain = normalize_domain(url_or_domain)

    if domain in TIER_1_DOMAINS:
        return DomainTier.TIER_1
    elif domain in TIER_2_DOMAINS:
        return DomainTier.TIER_2
    elif domain in TIER_3_DOMAINS:
        return DomainTier.TIER_3
    else:
        return DomainTier.TIER_4

# Source mix evaluation
def evaluate_source_mix(sources: list[dict]) -> dict:
    tiers = [get_domain_tier(s["url"]) for s in sources]

    if DomainTier.TIER_1 in tiers:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_IMMEDIATE",
            "verification_delay_minutes": 0
        }
    elif DomainTier.TIER_2 in tiers:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_WITH_VERIFICATION",
            "verification_delay_minutes": 60
        }
    elif len(set(normalize_domain(s["url"]) for s in sources)) >= 2:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_STANDARD",
            "verification_delay_minutes": 0
        }
    else:
        return {
            "can_publish": False,
            "recommended_action": "NEED_MORE_SOURCES"
        }
```

## Domain Lists

### Tier-1 (19 domains)
```python
TIER_1_DOMAINS = {
    "apnews.com", "reuters.com", "afp.com",
    "un.org", "nato.int", "who.int",
    "state.gov", "gov.uk", "europa.eu",
    "acleddata.com",
}
```

### Tier-2 (59 domains)
See `app/agent/source_tiers.py` for complete list.

### Tier-3 (37 domains)
See `app/agent/source_tiers.py` for complete list.

## References
- Implementation: `app/agent/source_tiers.py`
- Algorithm docs: `docs/en/algorithms/SOURCE_TIERS.md`
- Related ADR: [ADR-003: Tier System](ADR-003-tier-system.md) (trigger tiers)
- Related ADR: [ADR-007: Breaking News](ADR-007-breaking-news.md)
