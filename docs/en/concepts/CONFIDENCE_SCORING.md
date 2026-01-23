# Confidence Scoring

Every article in LiveMap includes a transparent confidence score that indicates how trustworthy the information is.

---

## Overview

Confidence scores range from **0.00 to 1.00** and are calculated based on:

1. **Number of sources** - More independent sources = higher confidence
2. **Source credibility** - Tier-1 sources weigh more than Tier-3
3. **Source diversity** - Different tier sources provide bonus

---

## Score Formula

```python
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus
```

### Components

| Component | Weight | Description |
|-----------|--------|-------------|
| Base Score | 50% | Based on source count |
| Tier Average | 50% | Average credibility of sources |
| Diversity Bonus | +0.03 | If sources from different tiers |

---

## Base Score (Source Count)

| Source Count | Base Score | Rationale |
|--------------|------------|-----------|
| 1 source | 0.50 | Single source = minimum confidence |
| 2 sources | 0.70 | Two-Source Rule satisfied |
| 3+ sources | 0.85 | Multiple independent confirmations |

---

## Tier Credibility Values

| Tier | Credibility |
|------|-------------|
| Tier-1 Govt | 0.99 |
| Tier-1 News | 0.90 |
| Tier-2 Data | 0.85 |
| Tier-2 News | 0.75 |
| Tier-3 Social | 0.40 |
| Tier-3 Msg | 0.35 |
| Tier-3 Trend | 0.30 |

---

## Calculation Examples

### Example 1: USGS Earthquake (Single Tier-1 Govt)

```
Sources: [USGS]
Tiers: [tier1_govt]

base_score = 0.50        # 1 source
tier_average = 0.99      # tier1_govt credibility
diversity_bonus = 0.00   # single tier

final = (0.50 × 0.5) + (0.99 × 0.5) + 0.00
      = 0.25 + 0.495 + 0.00
      = 0.745 → 0.74

Recommendation: immediate_publish (tier1_govt exception)
```

### Example 2: GDELT Article (Single Tier-1 News)

```
Sources: [GDELT]
Tiers: [tier1_news]

base_score = 0.50        # 1 source
tier_average = 0.90      # tier1_news credibility
diversity_bonus = 0.00   # single tier

final = (0.50 × 0.5) + (0.90 × 0.5) + 0.00
      = 0.25 + 0.45 + 0.00
      = 0.70

Recommendation: publishable
```

### Example 3: GDELT + Reddit (Multi-source)

```
Sources: [GDELT, Reddit]
Tiers: [tier1_news, tier3_social]

base_score = 0.70        # 2 sources
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = 0.03   # tier1 + tier3

final = (0.70 × 0.5) + (0.65 × 0.5) + 0.03
      = 0.35 + 0.325 + 0.03
      = 0.705 → 0.71

Two-source satisfied: Yes
Recommendation: publishable
```

### Example 4: Reddit Only (Single Tier-3)

```
Sources: [Reddit]
Tiers: [tier3_social]

base_score = 0.50        # 1 source
tier_average = 0.40      # tier3_social credibility
diversity_bonus = 0.00   # single tier

final = (0.50 × 0.5) + (0.40 × 0.5) + 0.00
      = 0.25 + 0.20 + 0.00
      = 0.45

Recommendation: do_not_publish (below 0.70 threshold)
```

### Example 5: Three Sources (High Confidence)

```
Sources: [GDELT, Currents, Reddit]
Tiers: [tier1_news, tier2_news, tier3_social]

base_score = 0.85        # 3+ sources
tier_average = (0.90 + 0.75 + 0.40) / 3 = 0.68
diversity_bonus = 0.03   # multiple tiers

final = (0.85 × 0.5) + (0.68 × 0.5) + 0.03
      = 0.425 + 0.34 + 0.03
      = 0.795 → 0.80

Two-source satisfied: Yes
Recommendation: high_confidence
```

---

## Confidence Levels

| Score Range | Level | Description |
|-------------|-------|-------------|
| 0.90+ | Very High | Multiple Tier-1 sources |
| 0.80-0.89 | High | 3+ sources or Tier-1 + Tier-2 |
| 0.70-0.79 | Medium | Meets publication threshold |
| 0.50-0.69 | Low | Needs more corroboration |
| < 0.50 | Very Low | Do not publish |

---

## Recommendations

| Recommendation | Criteria |
|----------------|----------|
| `immediate_publish` | Tier-1 Government source |
| `high_confidence` | Score ≥ 0.80 |
| `publishable` | Score ≥ 0.70 |
| `needs_corroboration` | Score 0.50-0.69 |
| `do_not_publish` | Score < 0.50 or single Tier-3 |

---

## Publication Threshold

The default minimum confidence score for publication is **0.70**.

```python
# config.py
min_confidence_score: float = 0.70
```

This ensures:
- Two-Source Rule satisfaction (base score 0.70)
- OR single Tier-1 source with high credibility

---

## Implementation

```python
# app/agent/confidence_scorer.py

def calculate_confidence(
    sources: list[dict],
) -> ConfidenceScore:
    """
    Calculate confidence score for an event.

    Args:
        sources: List of {"name": "gdelt", "tier": "tier1_news"}

    Returns:
        ConfidenceScore with score, level, and recommendation
    """
    source_count = len(sources)

    # Base score
    if source_count >= 3:
        base_score = 0.85
    elif source_count == 2:
        base_score = 0.70
    else:
        base_score = 0.50

    # Tier average
    tier_scores = [TIER_CREDIBILITY[s["tier"]] for s in sources]
    tier_average = sum(tier_scores) / len(tier_scores)

    # Diversity bonus
    unique_tiers = set(s["tier"] for s in sources)
    diversity_bonus = 0.03 if len(unique_tiers) > 1 else 0.00

    # Final score
    final_score = (base_score * 0.5) + (tier_average * 0.5) + diversity_bonus
    final_score = round(final_score, 2)

    return ConfidenceScore(
        score=final_score,
        level=get_confidence_level(final_score),
        recommendation=get_recommendation(final_score, sources),
        two_source_satisfied=(source_count >= 2),
    )
```

---

## Displaying Confidence

Articles show confidence as:

```json
{
  "title": "Iran launches missiles at US bases in Iraq",
  "confidence": {
    "score": 0.71,
    "level": "medium",
    "sources": ["GDELT", "Reddit"],
    "two_source_satisfied": true
  }
}
```

Users can filter articles by confidence level:
- Show only high confidence (≥0.80)
- Show all publishable (≥0.70)
- Show pending corroboration (0.50-0.69)

---

## Related Documentation

- [Two-Source Rule](TWO_SOURCE_RULE.md) - Verification requirements
- [Source Tiers](SOURCE_TIERS.md) - Tier definitions
- [Algorithm Details](../algorithms/CONFIDENCE_SCORING.md) - Implementation
