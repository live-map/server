# Confidence Scoring Algorithm

## Overview

The Confidence Scorer calculates a 0.0-0.99 score representing how trustworthy an event is based on its sources. This implements the Two-Source Rule from journalism.

## Score Components

The final score is computed from three components:

```
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus
```

### 1. Base Score (Source Count)

| Source Count | Base Score |
|--------------|------------|
| 0 | 0.00 |
| 1 | 0.50 |
| 2 | 0.70 |
| 3+ | 0.85 |

**Rationale:** More sources provide more verification.

### 2. Tier Average (Source Quality)

Average of tier weights for all sources:

| Tier | Weight | Sources |
|------|--------|---------|
| tier1_govt | 0.99 | USGS, NOAA |
| tier1_news | 0.90 | GDELT |
| tier2_data | 0.85 | ACLED |
| tier2_news | 0.75 | Currents, WorldNews |
| tier3_social | 0.40 | Reddit, Twitter |
| tier3_msg | 0.35 | Telegram |
| tier3_trend | 0.30 | Google Trends |

**Calculation:**
```python
tier_average = sum(tier_weights[s.tier] for s in sources) / len(sources)
```

### 3. Diversity Bonus

Bonus for having sources from different tier levels:

```python
diversity_bonus = (num_tier_types - 1) × 0.03
```

**Example:**
- Tier-1 + Tier-1: 0 bonus (same level)
- Tier-1 + Tier-3: 0.03 bonus (2 levels)
- Tier-1 + Tier-2 + Tier-3: 0.06 bonus (3 levels)

## Example Calculations

### Single GDELT Source
```
base_score = 0.50 (1 source)
tier_average = 0.90 (tier1_news)
diversity_bonus = 0.00 (1 tier type)

final = (0.50 × 0.5) + (0.90 × 0.5) + 0.00
      = 0.25 + 0.45 + 0.00
      = 0.70
```

### GDELT + Reddit
```
base_score = 0.70 (2 sources)
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = (2 - 1) × 0.03 = 0.03

final = (0.70 × 0.5) + (0.65 × 0.5) + 0.03
      = 0.35 + 0.325 + 0.03
      = 0.705
```

### GDELT + Currents + Reddit
```
base_score = 0.85 (3 sources)
tier_average = (0.90 + 0.75 + 0.40) / 3 = 0.683
diversity_bonus = (3 - 1) × 0.03 = 0.06

final = (0.85 × 0.5) + (0.683 × 0.5) + 0.06
      = 0.425 + 0.3415 + 0.06
      = 0.8265
```

## Confidence Levels

| Score Range | Level | Recommendation |
|-------------|-------|----------------|
| 0.85 - 0.99 | VERY_HIGH | immediate_publish |
| 0.70 - 0.84 | HIGH | publishable |
| 0.50 - 0.69 | MEDIUM | review_required |
| 0.00 - 0.49 | LOW | do_not_publish |

## Two-Source Rule

The Two-Source Rule is satisfied when:
1. **2+ independent sources**, OR
2. **Single Tier-1 government source** (USGS, NOAA)

```python
def _check_two_source_rule(sources: list[dict]) -> bool:
    if len(sources) == 1:
        return sources[0].get("tier") == "tier1_govt"
    return len(sources) >= 2
```

## Publication Decision

```python
def _determine_recommendation(score: float, sources: list[dict]):
    # Government sources always publishable
    if any(s.get("tier") == "tier1_govt" for s in sources):
        return PublishRecommendation.IMMEDIATE_PUBLISH

    # Score-based recommendation
    if score >= 0.85:
        return PublishRecommendation.IMMEDIATE_PUBLISH
    elif score >= 0.70:
        return PublishRecommendation.PUBLISHABLE
    elif score >= 0.50:
        return PublishRecommendation.REVIEW_REQUIRED
    else:
        return PublishRecommendation.DO_NOT_PUBLISH
```

## Score Cap

Scores are capped at 0.99:

```python
final_score = min(final_score, 0.99)
```

**Rationale:** Even with multiple high-tier sources, some uncertainty remains.

## Implementation

```python
# Usage
scorer = MultiSourceConfidenceScorer()
result = scorer.calculate_confidence([
    {"name": "GDELT", "tier": "tier1_news"},
    {"name": "Reddit", "tier": "tier3_social"},
])

print(result.score)  # 0.705
print(result.two_source_satisfied)  # True
print(result.recommendation)  # publishable
```

## Configuration

```python
MultiSourceConfidenceScorer(
    tier_weights=TIER_WEIGHTS,  # Custom weights if needed
    min_publish_confidence=0.70  # Publication threshold
)
```

## File Location

```
app/agent/confidence_scorer.py
```

## Related Documentation
- [Cross-Source Matcher](CROSS_SOURCE_MATCHER.md)
- [ADR-001: Two-Source Rule](../adr/ADR-001-two-source-rule.md)
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md)
