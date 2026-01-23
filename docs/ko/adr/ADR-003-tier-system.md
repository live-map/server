# ADR-003: Tier Classification System

## Status
Accepted

## Context

우리 시스템은 신뢰도 수준이 크게 다른 여러 출처에서 뉴스를 집계합니다:
- 정부 기관(USGS, NOAA)은 권위 있는 데이터를 게시함
- 주요 뉴스 집계업체(Reuters, AP를 통한 GDELT)는 편집 감독이 있음
- 뉴스 API는 다양한 퍼블리셔에서 집계함
- 소셜 미디어는 검증되지 않은 사용자 생성 콘텐츠를 포함함

다음을 위한 체계적인 방법이 필요했습니다:
1. 출처 신뢰도를 정량화
2. 신뢰도 점수에서 출처에 가중치 부여
3. 적절한 검증 요구사항 적용
4. 검증 결정을 투명하게 만들기

## Decision

7개의 하위 카테고리가 있는 3단계 출처 분류 시스템을 구현합니다:

### Tier Structure

| Tier | Sub-Tier | Weight | Sources | Characteristics |
|------|----------|--------|---------|-----------------|
| **Tier-1** | `tier1_govt` | 0.99 | USGS, NOAA, EMSC | 공식 정부 데이터 |
| | `tier1_news` | 0.90 | GDELT (Reuters, AP, BBC) | 주요 뉴스 집계업체 |
| **Tier-2** | `tier2_data` | 0.85 | ACLED | 연구/학술 데이터 |
| | `tier2_news` | 0.75 | Currents, WorldNews API | 보조 뉴스 API |
| **Tier-3** | `tier3_social` | 0.40 | Reddit, Twitter, Bluesky | 소셜 미디어 플랫폼 |
| | `tier3_msg` | 0.35 | Telegram | 메시징 플랫폼 |
| | `tier3_trend` | 0.30 | Google Trends | 트렌드 지표 |

### Weight Rationale

**Tier-1 (0.90-0.99)**: 1차 출처
- 정부 출처는 0.99 (공식 데이터에 대해 본질적으로 완벽한 신뢰도)
- 주요 뉴스는 0.90 (매우 신뢰할 수 있지만 오류가 있을 수 있음)

**Tier-2 (0.75-0.85)**: 2차 출처
- 연구 데이터는 0.85 (검증되었지만 지연이 있을 수 있음)
- 뉴스 API는 0.75 (집계 품질이 다양함)

**Tier-3 (0.30-0.40)**: 신호 출처
- 소셜 미디어는 0.40 (초기 신호지만 검증되지 않음)
- 메시징은 0.35 (덜 구조적이고 노이즈가 많음)
- 트렌드는 0.30 (지표일 뿐, 직접적인 보도가 아님)

### Confidence Score Formula

```python
final_score = (base_score * 0.5) + (tier_average * 0.5) + diversity_bonus
```

여기서:
- `base_score`: 출처 수에 기반 (0.50/0.70/0.85)
- `tier_average`: 티어 가중치의 평균
- `diversity_bonus`: 추가 티어 유형당 0.03

## Consequences

### Positive
- 명확하고 정량화 가능한 신뢰도 계층
- 모든 출처에 대한 일관된 처리
- Two-Source Rule 구현 지원
- 감사를 위한 투명한 점수
- 새 출처를 적절한 티어에 쉽게 추가 가능

### Negative
- 정적 가중치가 출처 평판 변화를 반영하지 못할 수 있음
- 티어 내 개별 퍼블리셔 품질이 다양함
- 일부 출처가 처음에 잘못 분류될 수 있음
- 티어 할당의 정기적인 검토가 필요함

## Alternatives Considered

### Alternative A: Per-Source Reputation Scores
각 출처에 개별 평판 점수를 할당합니다.

**기각 사유:**
- 추적할 잠재적 출처가 수백 개임
- 정확한 점수를 유지하기 어려움
- 복잡한 평판 추적 시스템이 필요함
- 사용자에게 설명하기 어려움

### Alternative B: Binary Trusted/Untrusted
간단한 2단계 시스템: 신뢰할 수 있는 출처와 신뢰할 수 없는 출처.

**기각 사유:**
- 미묘한 결정에는 너무 조잡함
- 신뢰도를 정확하게 가중치 부여할 수 없음
- 실제 세계의 신뢰도 스펙트럼을 반영하지 않음
- 보조 출처에 대한 중간 지대가 없음

### Alternative C: Dynamic ML-Based Scoring
ML 모델을 훈련시켜 출처 신뢰도를 예측합니다.

**기각 사유:**
- 블랙박스 의사결정
- 레이블이 지정된 훈련 데이터가 필요함
- 편향을 학습할 수 있음
- 유지 관리 비용이 많이 듦

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
- 구현: `app/agent/triggers/base.py`
- 신뢰도 점수: `app/agent/confidence_scorer.py`
- 프로젝트 문서: `docs/concepts/README.md`
