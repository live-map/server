# ADR-003: Trigger Tier Classification System

## Status
Accepted (Updated January 2026)

## Note on Tier Systems

This ADR describes the **Trigger Tier System** for classifying data source APIs (GDELT, USGS, Reddit, etc.).

A separate **Domain Tier System** was introduced in [ADR-011](ADR-011-domain-tiers.md) for classifying individual news domains (reuters.com, bbc.com, etc.). The two systems work together:

- **Trigger Tiers**: Classify the data source/API (where we get data from)
- **Domain Tiers**: Classify the content publisher (who wrote the article)

## Context

Our system aggregates news from multiple trigger sources with vastly different credibility levels:
- Government agencies (USGS, NOAA) publish authoritative data
- Major news aggregators (GDELT via Reuters, AP) have editorial oversight
- News APIs aggregate from various publishers
- Social media contains unverified user-generated content

We needed a systematic way to:
1. Quantify source credibility
2. Weight sources in confidence scoring
3. Apply appropriate verification requirements
4. Make verification decisions transparent

## Decision

Implement a 3-tier source classification system with 7 sub-categories:

### Tier Structure

| Tier | Sub-Tier | Weight | Sources | Characteristics |
|------|----------|--------|---------|-----------------|
| **Tier-1** | `tier1_govt` | 0.99 | USGS, NOAA, EMSC | Official government data |
| | `tier1_news` | 0.90 | GDELT (Reuters, AP, BBC) | Major news aggregators |
| **Tier-2** | `tier2_data` | 0.85 | ACLED | Research/academic data |
| | `tier2_news` | 0.75 | Currents, WorldNews API | Secondary news APIs |
| **Tier-3** | `tier3_social` | 0.40 | Reddit, Twitter, Bluesky | Social media platforms |
| | `tier3_msg` | 0.35 | Telegram | Messaging platforms |
| | `tier3_trend` | 0.30 | Google Trends | Trend indicators |

### Weight Rationale

**Tier-1 (0.90-0.99)**: Primary sources
- Government sources get 0.99 (essentially perfect credibility for official data)
- Major news at 0.90 (highly credible but can have errors)

**Tier-2 (0.75-0.85)**: Secondary sources
- Research data at 0.85 (verified but may have delay)
- News APIs at 0.75 (aggregation varies in quality)

**Tier-3 (0.30-0.40)**: Signal sources
- Social media at 0.40 (early signals but unverified)
- Messaging at 0.35 (less structured, more noise)
- Trends at 0.30 (indicators only, not direct reports)

### Confidence Score Formula

```python
final_score = (base_score * 0.5) + (tier_average * 0.5) + diversity_bonus
```

Where:
- `base_score`: Based on source count (0.50/0.70/0.85)
- `tier_average`: Average of tier weights
- `diversity_bonus`: 0.03 per additional tier type

## Consequences

### Positive
- Clear, quantifiable credibility hierarchy
- Consistent treatment across all sources
- Supports Two-Source Rule implementation
- Transparent scoring for auditing
- Easy to add new sources to appropriate tier

### Negative
- Static weights may not capture source reputation changes
- Individual publisher quality within tiers varies
- Some sources may be mis-categorized initially
- Requires periodic review of tier assignments

## Alternatives Considered

### Alternative A: Per-Source Reputation Scores
Assign individual reputation scores to each source.

**Rejected because:**
- Hundreds of potential sources to track
- Difficult to maintain accurate scores
- Requires complex reputation tracking system
- Harder to explain to users

### Alternative B: Binary Trusted/Untrusted
Simple two-tier system: trusted and untrusted sources.

**Rejected because:**
- Too coarse for nuanced decisions
- Can't weight confidence accurately
- Doesn't reflect real-world credibility spectrum
- No middle ground for secondary sources

### Alternative C: Dynamic ML-Based Scoring
Train ML model to predict source credibility.

**Rejected because:**
- Black-box decision making
- Requires labeled training data
- May learn biases
- Expensive to maintain

## Implementation

```python
# Source tier mapping
SOURCE_TIER_MAP = {
    TriggerSource.USGS: SourceTier.TIER1_GOVT,
    TriggerSource.NOAA: SourceTier.TIER1_GOVT,
    TriggerSource.GDELT: SourceTier.TIER1_NEWS,
    TriggerSource.CURRENTS: SourceTier.TIER2_NEWS,
    TriggerSource.REDDIT: SourceTier.TIER3_SOCIAL,
    # ...
}

# Tier weights
TIER_WEIGHTS = {
    SourceTier.TIER1_GOVT.value: 0.99,
    SourceTier.TIER1_NEWS.value: 0.90,
    SourceTier.TIER2_DATA.value: 0.85,
    SourceTier.TIER2_NEWS.value: 0.75,
    SourceTier.TIER3_SOCIAL.value: 0.40,
    SourceTier.TIER3_MSG.value: 0.35,
    SourceTier.TIER3_TREND.value: 0.30,
}
```

## References
- Implementation: `app/agent/triggers/base.py`
- Confidence scoring: `app/agent/confidence_scorer.py`
- Project docs: `docs/concepts/README.md`

## Related ADRs
- [ADR-011: Domain Tiers](ADR-011-domain-tiers.md) - Per-domain credibility (complements this ADR)
- [ADR-007: Breaking News](ADR-007-breaking-news.md) - Uses both tier systems
- [ADR-001: Two-Source Rule](ADR-001-two-source-rule.md) - Publication requirements
