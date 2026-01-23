# Confidence Scoring Algorithm

## Overview

Confidence Scorer는 소스를 기반으로 이벤트의 신뢰도를 나타내는 0.0-0.99 점수를 계산합니다. 이는 저널리즘의 Two-Source Rule을 구현한 것입니다.

## Score Components

최종 점수는 세 가지 구성 요소로 계산됩니다:

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

**근거:** 소스가 많을수록 더 많은 검증이 가능합니다.

### 2. Tier Average (Source Quality)

모든 소스에 대한 tier 가중치의 평균:

| Tier | Weight | Sources |
|------|--------|---------|
| tier1_govt | 0.99 | USGS, NOAA |
| tier1_news | 0.90 | GDELT |
| tier2_data | 0.85 | ACLED |
| tier2_news | 0.75 | Currents, WorldNews |
| tier3_social | 0.40 | Reddit, Twitter |
| tier3_msg | 0.35 | Telegram |
| tier3_trend | 0.30 | Google Trends |

**계산:**
```python
tier_average = sum(tier_weights[s.tier] for s in sources) / len(sources)
```

### 3. Diversity Bonus

서로 다른 tier 레벨의 소스를 보유할 경우 보너스:

```python
diversity_bonus = (num_tier_types - 1) × 0.03
```

**예시:**
- Tier-1 + Tier-1: 0 보너스 (동일 레벨)
- Tier-1 + Tier-3: 0.03 보너스 (2개 레벨)
- Tier-1 + Tier-2 + Tier-3: 0.06 보너스 (3개 레벨)

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

Two-Source Rule은 다음 조건에서 충족됩니다:
1. **2개 이상의 독립적인 소스**, 또는
2. **단일 Tier-1 정부 소스** (USGS, NOAA)

```python
def _check_two_source_rule(sources: list[dict]) -> bool:
    if len(sources) == 1:
        return sources[0].get("tier") == "tier1_govt"
    return len(sources) >= 2
```

## Publication Decision

```python
def _determine_recommendation(score: float, sources: list[dict]):
    # 정부 소스는 항상 게시 가능
    if any(s.get("tier") == "tier1_govt" for s in sources):
        return PublishRecommendation.IMMEDIATE_PUBLISH

    # 점수 기반 권장 사항
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

점수는 0.99로 제한됩니다:

```python
final_score = min(final_score, 0.99)
```

**근거:** 여러 고tier 소스가 있더라도 약간의 불확실성은 항상 존재합니다.

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
    tier_weights=TIER_WEIGHTS,  # 필요시 커스텀 가중치
    min_publish_confidence=0.70  # 게시 임계값
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
