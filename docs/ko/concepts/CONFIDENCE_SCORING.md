# Confidence Scoring (신뢰도 점수)

LiveMap의 모든 기사에는 정보가 얼마나 신뢰할 수 있는지를 나타내는 투명한 신뢰도 점수가 포함됩니다.

---

## 개요

신뢰도 점수는 **0.00부터 1.00**까지이며 다음을 기반으로 계산됩니다:

1. **소스 수** - 더 많은 독립 소스 = 더 높은 신뢰도
2. **소스 신뢰도** - Tier-1 소스가 Tier-3보다 높은 가중치
3. **소스 다양성** - 다른 티어 소스가 보너스 제공

---

## 점수 공식

```python
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus
```

### 구성 요소

| 구성 요소 | 가중치 | 설명 |
|-----------|--------|-------------|
| Base Score | 50% | 소스 수 기반 |
| Tier Average | 50% | 소스들의 평균 신뢰도 |
| Diversity Bonus | +0.03 | 다른 티어의 소스가 있는 경우 |

---

## Base Score (소스 수)

| 소스 수 | Base Score | 근거 |
|--------------|------------|-----------|
| 1 소스 | 0.50 | 단일 소스 = 최소 신뢰도 |
| 2 소스 | 0.70 | Two-Source Rule 충족 |
| 3+ 소스 | 0.85 | 다중 독립 확인 |

---

## Tier 신뢰도 값

| Tier | 신뢰도 |
|------|-------------|
| Tier-1 정부 | 0.99 |
| Tier-1 뉴스 | 0.90 |
| Tier-2 데이터 | 0.85 |
| Tier-2 뉴스 | 0.75 |
| Tier-3 소셜 | 0.40 |
| Tier-3 메시징 | 0.35 |
| Tier-3 트렌드 | 0.30 |

---

## 계산 예시

### 예시 1: USGS 지진 (단일 Tier-1 정부)

```
소스: [USGS]
티어: [tier1_govt]

base_score = 0.50        # 1 소스
tier_average = 0.99      # tier1_govt 신뢰도
diversity_bonus = 0.00   # 단일 티어

final = (0.50 × 0.5) + (0.99 × 0.5) + 0.00
      = 0.25 + 0.495 + 0.00
      = 0.745 → 0.74

권장: immediate_publish (tier1_govt 예외)
```

### 예시 2: GDELT 기사 (단일 Tier-1 뉴스)

```
소스: [GDELT]
티어: [tier1_news]

base_score = 0.50        # 1 소스
tier_average = 0.90      # tier1_news 신뢰도
diversity_bonus = 0.00   # 단일 티어

final = (0.50 × 0.5) + (0.90 × 0.5) + 0.00
      = 0.25 + 0.45 + 0.00
      = 0.70

권장: publishable
```

### 예시 3: GDELT + Reddit (다중 소스)

```
소스: [GDELT, Reddit]
티어: [tier1_news, tier3_social]

base_score = 0.70        # 2 소스
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = 0.03   # tier1 + tier3

final = (0.70 × 0.5) + (0.65 × 0.5) + 0.03
      = 0.35 + 0.325 + 0.03
      = 0.705 → 0.71

Two-source 충족: 예
권장: publishable
```

### 예시 4: Reddit 단독 (단일 Tier-3)

```
소스: [Reddit]
티어: [tier3_social]

base_score = 0.50        # 1 소스
tier_average = 0.40      # tier3_social 신뢰도
diversity_bonus = 0.00   # 단일 티어

final = (0.50 × 0.5) + (0.40 × 0.5) + 0.00
      = 0.25 + 0.20 + 0.00
      = 0.45

권장: do_not_publish (0.70 임계값 미만)
```

### 예시 5: 세 소스 (높은 신뢰도)

```
소스: [GDELT, Currents, Reddit]
티어: [tier1_news, tier2_news, tier3_social]

base_score = 0.85        # 3+ 소스
tier_average = (0.90 + 0.75 + 0.40) / 3 = 0.68
diversity_bonus = 0.03   # 다중 티어

final = (0.85 × 0.5) + (0.68 × 0.5) + 0.03
      = 0.425 + 0.34 + 0.03
      = 0.795 → 0.80

Two-source 충족: 예
권장: high_confidence
```

---

## 신뢰도 수준

| 점수 범위 | 수준 | 설명 |
|-------------|-------|-------------|
| 0.90+ | 매우 높음 | 다중 Tier-1 소스 |
| 0.80-0.89 | 높음 | 3+ 소스 또는 Tier-1 + Tier-2 |
| 0.70-0.79 | 중간 | 게시 임계값 충족 |
| 0.50-0.69 | 낮음 | 추가 확인 필요 |
| < 0.50 | 매우 낮음 | 게시 안 함 |

---

## 권장 사항

| 권장 | 기준 |
|----------------|----------|
| `immediate_publish` | Tier-1 정부 소스 |
| `high_confidence` | 점수 ≥ 0.80 |
| `publishable` | 점수 ≥ 0.70 |
| `needs_corroboration` | 점수 0.50-0.69 |
| `do_not_publish` | 점수 < 0.50 또는 단일 Tier-3 |

---

## 게시 임계값

기본 최소 신뢰도 점수는 **0.70**입니다.

```python
# config.py
min_confidence_score: float = 0.70
```

이것은 다음을 보장합니다:
- Two-Source Rule 충족 (base score 0.70)
- 또는 높은 신뢰도를 가진 단일 Tier-1 소스

---

## 구현

```python
# app/agent/confidence_scorer.py

def calculate_confidence(
    sources: list[dict],
) -> ConfidenceScore:
    """
    이벤트의 신뢰도 점수를 계산합니다.

    Args:
        sources: [{"name": "gdelt", "tier": "tier1_news"}] 리스트

    Returns:
        점수, 수준, 권장을 포함한 ConfidenceScore
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

## 신뢰도 표시

기사에서 신뢰도는 다음과 같이 표시됩니다:

```json
{
  "title": "이란, 이라크 내 미군 기지에 미사일 발사",
  "confidence": {
    "score": 0.71,
    "level": "medium",
    "sources": ["GDELT", "Reddit"],
    "two_source_satisfied": true
  }
}
```

사용자는 신뢰도 수준으로 기사를 필터링할 수 있습니다:
- 높은 신뢰도만 표시 (≥0.80)
- 모든 게시 가능 표시 (≥0.70)
- 확인 대기 중 표시 (0.50-0.69)

---

## 관련 문서

- [Two-Source Rule](TWO_SOURCE_RULE.md) - 검증 요구사항
- [Source Tiers](SOURCE_TIERS.md) - 티어 정의
- [알고리즘 상세](../algorithms/CONFIDENCE_SCORING.md) - 구현
