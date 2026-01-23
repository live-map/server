# ADR-XXX: [제목]

## Status
[Proposed | Accepted | Deprecated | Superseded]

> 대체된 경우, 새 ADR로 연결: Superseded by [ADR-XXX](./ADR-XXX-title.md)

## Context

[이 결정을 내리게 된 상황을 설명합니다. 해결하려는 문제는 무엇인가? 제약 조건은 무엇인가? 어떤 요소들이 작용하는가?]

### Background

[선택사항: 맥락 이해를 돕는 추가 배경 정보를 제공합니다.]

### Requirements

[선택사항: 충족해야 할 구체적인 요구사항을 나열합니다.]

## Decision

[내려진 결정을 설명합니다. 무엇을 하는지 구체적이고 명확하게 작성합니다.]

### Implementation

[선택사항: 결정이 어떻게 구현될지 설명합니다. 코드 예시가 도움이 된다면 포함합니다.]

```python
# Example code showing the implementation
def example_function():
    pass
```

### Configuration

[선택사항: 필요한 설정 변경 사항을 나열합니다.]

| Setting | Value | Description |
|---------|-------|-------------|
| `SETTING_NAME` | `value` | 설명 |

## Consequences

### Positive

- [이 결정의 장점을 나열합니다]
- [또 다른 장점]

### Negative

- [단점이나 리스크를 나열합니다]
- [또 다른 단점]

### Neutral

- [선택사항: 긍정도 부정도 아닌 변경사항을 나열합니다]

## Alternatives Considered

### Alternative A: [이름]

[대안을 설명합니다]

**기각 사유:**
- [사유 1]
- [사유 2]

### Alternative B: [이름]

[대안을 설명합니다]

**기각 사유:**
- [사유 1]
- [사유 2]

## References

- [관련 문서 링크]
- 구현: `path/to/file.py`
- 관련 ADR: [ADR-XXX](./ADR-XXX-title.md)

---

## ADR 명명 규칙

ADR은 다음과 같이 명명합니다: `ADR-XXX-short-title.md`

여기서:
- `XXX`는 순차적인 번호입니다 (001, 002 등)
- `short-title`은 kebab-case 설명입니다 (예: `two-source-rule`, `hybrid-verification`)

## ADR 프로세스

1. **Propose**: "Proposed" 상태로 새 ADR을 생성합니다
2. **Discuss**: 팀과 함께 검토합니다
3. **Accept**: 승인되면 상태를 "Accepted"로 변경합니다
4. **Implement**: 솔루션을 구현합니다
5. **Update**: 나중에 변경되면 "Deprecated" 또는 "Superseded"로 표시합니다

## 기존 ADR 목록

| ADR | 제목 | 상태 |
|-----|-------|--------|
| [ADR-001](./ADR-001-two-source-rule.md) | Two-Source Rule | Accepted |
| [ADR-002](./ADR-002-gate-ordering.md) | Gate Ordering | Accepted |
| [ADR-003](./ADR-003-tier-system.md) | Tier Classification System | Accepted |
| [ADR-004](./ADR-004-hybrid-verification.md) | Hybrid Event Verification | Accepted |
