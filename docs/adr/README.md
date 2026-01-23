# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the LiveMap backend system.

## What is an ADR?

An Architecture Decision Record (ADR) captures an important architectural decision made along with its context and consequences.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](ADR-001-two-source-rule.md) | Two-Source Rule | Accepted | 2024-01 |
| [ADR-002](ADR-002-gate-ordering.md) | Gate Ordering | Accepted | 2024-01 |
| [ADR-003](ADR-003-tier-system.md) | Tier Classification System | Accepted | 2024-01 |
| [ADR-004](ADR-004-hybrid-verification.md) | Hybrid Event Verification | Accepted | 2024-01 |
| [ADR-005](ADR-005-bilingual-generation.md) | Bilingual Article Generation | Accepted | 2024-01 |
| [ADR-006](ADR-006-deduplication.md) | Two-Layer Deduplication | Accepted | 2024-01 |

## ADR Template

```markdown
# ADR-XXX: [Title]

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-YYY

## Context
[Why was this decision needed? What problem were we trying to solve?]

## Decision
[What was the decision that was made?]

## Consequences
### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Drawback 1]
- [Drawback 2]

## Alternatives Considered
### Alternative A
[Description and why it wasn't chosen]

### Alternative B
[Description and why it wasn't chosen]
```
