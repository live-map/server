# ADR-002: Gate Ordering

## Status
Accepted

## Context

스캐너 파이프라인은 원시 이벤트를 여러 필터링 단계(게이트)를 통해 처리합니다. 각 게이트는 다음과 같은 특성이 다릅니다:
- **비용**: CPU 시간, LLM API 호출, 데이터베이스 쿼리
- **필터링 능력**: 거부되는 이벤트의 비율
- **의존성**: 일부 게이트는 이전 처리 결과가 필요함

최적의 순서를 결정해야 했습니다:
1. 처리 비용 최소화
2. 필터링 효율성 최대화
3. 논리적 데이터 흐름 유지

## Decision

다음 순서로 게이트를 구현합니다:

```
Gate 0: Event Verification (Hybrid Rule + LLM)
  ↓ ~70% filtered by rules, ~30% require LLM
Gate 1: Check-worthiness (Pattern-based)
  ↓ Filters entertainment, speculation, promotions
Gate 2: Specificity (Pattern-based)
  ↓ Filters vague, generic content
Gate 3: Evidence Sufficiency (Claim verification)
  ↓ Filters unverified claims
```

### Gate Details

| Gate | Type | Cost | Filter Rate | Purpose |
|------|------|------|-------------|---------|
| 0 | Hybrid | Low-Medium | ~70% | 실제 이벤트 vs 비이벤트 |
| 1 | Pattern | Very Low | ~15% | 뉴스 가치 vs 엔터테인먼트 |
| 2 | Pattern | Very Low | ~10% | 구체적 vs 모호함 |
| 3 | LLM | High | ~5% | 증거 검증 |

### Rationale for Ordering

1. **Gate 0 우선 (Event Verification)**
   - 규칙이 70%를 무료로 필터링 ($0)
   - 30%만 LLM 검증이 필요 ($0.001/이벤트)
   - 비용이 많이 드는 처리 전에 비이벤트를 제거

2. **Gate 1 두 번째 (Check-worthiness)**
   - 순수 패턴 매칭 (마이크로초)
   - 엔터테인먼트/추측을 빠르게 제거
   - 후속 게이트의 부하를 줄임

3. **Gate 2 세 번째 (Specificity)**
   - 패턴 기반 (마이크로초)
   - 영어 전용 패턴 (비영어 건너뜀)
   - 후보 집합을 더욱 줄임

4. **Gate 3 마지막 (Evidence)**
   - 가장 비용이 많이 듦 (LLM 기반)
   - 검증된, 뉴스 가치가 있는, 구체적인 이벤트만 처리
   - 가능한 가장 작은 집합에 적용됨

## Consequences

### Positive
- 비용 효율적: 가장 저렴한 필터가 먼저
- 빠른 거부: 대부분의 이벤트가 빠르게 거부됨
- 리소스 최적화: 비싼 작업을 최소화
- 명확한 논리적 흐름: 각 게이트가 이전 것을 기반으로 함
- 쉬운 디버깅: 실패를 특정 게이트로 추적 가능

### Negative
- Tier-1 정부 출처는 일부 게이트를 우회함 (필요한 트레이드오프)
- 비영어 콘텐츠는 Gate 2를 건너뜀 (패턴 제한)
- 게이트 순서가 긴밀하게 결합됨
- 순서 변경에는 신중한 분석이 필요함

## Alternatives Considered

### Alternative A: Parallel Gate Processing
모든 게이트를 동시에 실행하고 결과를 결합합니다.

**기각 사유:**
- 초기 게이트에서 실패할 이벤트를 처리하여 리소스 낭비
- 더 복잡한 결과 병합 로직
- 비용 절감 이점 없음
- 필터링 결정 디버깅이 어려움

### Alternative B: ML-Based Single Gate
단일 ML 모델을 훈련시켜 모든 원하지 않는 콘텐츠를 필터링합니다.

**기각 사유:**
- 블랙박스 의사결정
- 비싼 훈련 및 추론
- 거부 이유 설명이 어려움
- 단일 장애점

### Alternative C: Reverse Order (Expensive First)
패턴 매칭 전에 증거 검증을 실행합니다.

**기각 사유:**
- 10배 높은 API 비용
- 전체 처리가 더 느림
- 논리적 이점 없음
- 엔터테인먼트 콘텐츠에 LLM 호출 낭비

## Implementation

```python
# Stage 3.5: Event Verification (Gate 0)
if agent_settings.event_verification_enabled:
    verified_events = await self._verify_events(events)

# Stage 4: Check-worthiness (Gate 1)
if agent_settings.checkworthiness_enabled:
    checkworthy_events = self._filter_checkworthy(verified_events)

# Stage 5: Specificity (Gate 2)
if agent_settings.specificity_enabled:
    specific_events = self._filter_specific(checkworthy_events)

# Stage 6: Evidence (Gate 3)
if agent_settings.evidence_gate_enabled:
    verified_claims = await self._verify_claims(specific_events)
```

## References
- 구현: `app/agent/scanner.py:_classify_and_group()`
- Gate 0: `app/agent/event_verifier.py`
- Gate 1: `app/agent/checkworthiness.py`
- Gate 2: `app/agent/specificity.py`
