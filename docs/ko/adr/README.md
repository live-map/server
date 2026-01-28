# Architecture Decision Records (ADRs)

이 디렉토리에는 LiveMap 백엔드 시스템의 아키텍처 결정 기록이 포함되어 있습니다.

## ADR이란?

Architecture Decision Record (ADR)는 중요한 아키텍처 결정과 그 맥락 및 결과를 기록한 문서입니다.

## ADR 목록

| ADR | 제목 | 상태 | 날짜 |
|-----|-------|--------|------|
| [ADR-001](ADR-001-two-source-rule.md) | Two-Source Rule | Accepted | 2026-01-10 |
| [ADR-002](ADR-002-gate-ordering.md) | Gate Ordering | Accepted | 2026-01-15 |
| [ADR-003](ADR-003-tier-system.md) | 트리거 티어 시스템 | Accepted | 2026-01-11 |
| [ADR-004](ADR-004-hybrid-verification.md) | Hybrid Event Verification | Accepted | 2026-01-21 |
| [ADR-005](ADR-005-bilingual-generation.md) | Bilingual Article Generation | Accepted | 2026-01-23 |
| [ADR-006](ADR-006-deduplication.md) | Two-Layer Deduplication | Accepted | 2026-01-21 |
| [ADR-007](ADR-007-breaking-news.md) | 속보 패스트패스 | Accepted | 2026-01-24 |
| [ADR-008](ADR-008-importance-scoring.md) | Goldstein Scale 중요도 | Accepted | 2026-01-24 |
| [ADR-011](ADR-011-domain-tiers.md) | 도메인 티어 시스템 | Accepted | 2026-01-24 |
| [ADR-012](ADR-012-llm-classifier.md) | **LLM 분류기 (패턴 대체)** | Accepted | 2026-01-27 |

## ADR 템플릿

```markdown
# ADR-XXX: [제목]

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-YYY

## Context
[이 결정이 필요했던 이유는 무엇인가? 어떤 문제를 해결하려 했는가?]

## Decision
[어떤 결정이 내려졌는가?]

## Consequences
### Positive
- [장점 1]
- [장점 2]

### Negative
- [단점 1]
- [단점 2]

## Alternatives Considered
### Alternative A
[대안 설명 및 선택하지 않은 이유]

### Alternative B
[대안 설명 및 선택하지 않은 이유]
```
