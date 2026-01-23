# ADR-001: Two-Source Rule

## Status
Accepted

## Context

뉴스 검증 시스템은 출판 속도와 정확성 사이의 균형이라는 중요한 과제에 직면해 있습니다. 단일 출처 보도는 다음과 같은 문제가 있을 수 있습니다:
- 부정확하거나 오해의 소지가 있음
- 문맥에서 벗어남
- 의도적으로 허위일 수 있음 (허위정보)
- 불완전하거나 예비적임

언론 업계에서는 "Two-Source Rule"을 오랫동안 표준 관행으로 사용해 왔습니다: 주장을 게시하기 전에 최소한 두 개의 출처에서 독립적으로 검증해야 합니다.

대량의 실시간 뉴스를 처리하면서도 자동화된 시스템이 언론 윤리를 유지할 수 있도록 체계적인 접근 방식이 필요했습니다.

## Decision

Two-Source Rule을 핵심 검증 원칙으로 구현합니다:

### Primary Rule
이벤트는 게시 전에 최소 **2개의 독립적인 출처**에서 검증되어야 합니다.

### Exception for Tier-1 Government Sources
단일 Tier-1 정부 출처(USGS, NOAA)로도 충분한 이유:
- 공식적인 1차 데이터 소스임
- 데이터가 정의상 권위가 있음
- 교차 검증을 기다리면 중요한 알림이 지연됨 (지진, 악천후)

### Implementation
```python
def _check_two_source_rule(self, sources: list[dict]) -> bool:
    # Single Tier-1 govt source is sufficient
    if len(sources) == 1:
        tier = sources[0].get("tier", "")
        return tier == SourceTier.TIER1_GOVT.value

    # Two or more independent sources
    return len(sources) >= 2
```

### Confidence Score Impact
- 단일 출처 (비정부): 기본 점수 0.50 (게시 불가)
- 두 개 출처: 기본 점수 0.70 (게시 가능)
- 세 개 이상 출처: 기본 점수 0.85 (높은 신뢰도)

## Consequences

### Positive
- 거짓 양성률을 크게 줄임
- 확립된 언론 표준과 일치함
- 일관된 정확성으로 사용자 신뢰를 구축함
- 정부 데이터 바이패스로 중요한 지연을 방지함
- 명확하고 감사 가능한 검증 기준

### Negative
- 일부 실제 이벤트가 교차 검증될 때까지 지연될 수 있음
- 단일 출처 속보는 즉시 게시할 수 없음
- 효과적인 교차 출처 매칭 알고리즘이 필요함
- 하나의 출처에서만 보도된 이벤트를 놓칠 수 있음

## Alternatives Considered

### Alternative A: Single Source with High Confidence Threshold
신뢰도 점수가 0.90을 초과하면 단일 출처에서 게시합니다.

**기각 사유:**
- 신뢰도 점수만으로는 정확성을 보장할 수 없음
- 높은 등급의 출처도 부정확하게 보도할 수 있음
- 독립적인 검증 메커니즘이 없음

### Alternative B: LLM-Based Verification Only
LLM을 사용하여 단일 출처 보도의 진실성을 평가합니다.

**기각 사유:**
- LLM은 환각을 일으키거나 속을 수 있음
- 실제 세계 검증에 근거하지 않음
- 대규모로는 비용이 많이 듦 (검증당 $0.001 이상)
- 실제 검증 없이 지연만 추가됨

### Alternative C: Time-Based Publication
반박하는 출처가 없으면 N분 후에 게시합니다.

**기각 사유:**
- 반박의 부재는 검증이 아님
- 임의적인 시간 임계값
- 출처가 느리면 허위정보를 게시할 수 있음

## References
- [Two-Source Rule in Journalism](https://en.wikipedia.org/wiki/Confirmation_by_two_sources)
- 프로젝트 문서: `docs/concepts/README.md`
- 구현: `app/agent/confidence_scorer.py`
