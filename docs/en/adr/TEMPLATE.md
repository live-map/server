# ADR-XXX: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded]

> If superseded, link to the new ADR: Superseded by [ADR-XXX](./ADR-XXX-title.md)

## Context

[Describe the situation that led to this decision. What is the problem we're trying to solve? What are the constraints? What are the forces at play?]

### Background

[Optional: Provide additional background information that helps understand the context.]

### Requirements

[Optional: List specific requirements that must be met.]

## Decision

[Describe the decision that was made. Be specific and clear about what we're doing.]

### Implementation

[Optional: Describe how the decision will be implemented. Include code examples if helpful.]

```python
# Example code showing the implementation
def example_function():
    pass
```

### Configuration

[Optional: List any configuration changes required.]

| Setting | Value | Description |
|---------|-------|-------------|
| `SETTING_NAME` | `value` | Description |

## Consequences

### Positive

- [List the benefits of this decision]
- [Another benefit]

### Negative

- [List the drawbacks or risks]
- [Another drawback]

### Neutral

- [Optional: List changes that are neither positive nor negative]

## Alternatives Considered

### Alternative A: [Name]

[Describe the alternative]

**Rejected because:**
- [Reason 1]
- [Reason 2]

### Alternative B: [Name]

[Describe the alternative]

**Rejected because:**
- [Reason 1]
- [Reason 2]

## References

- [Link to relevant documentation]
- Implementation: `path/to/file.py`
- Related ADR: [ADR-XXX](./ADR-XXX-title.md)

---

## ADR Naming Convention

ADRs should be named: `ADR-XXX-short-title.md`

Where:
- `XXX` is a sequential number (001, 002, etc.)
- `short-title` is a kebab-case description (e.g., `two-source-rule`, `hybrid-verification`)

## ADR Process

1. **Propose**: Create a new ADR with status "Proposed"
2. **Discuss**: Review with the team
3. **Accept**: Change status to "Accepted" when approved
4. **Implement**: Build the solution
5. **Update**: Mark as "Deprecated" or "Superseded" if changed later

## Existing ADRs

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](./ADR-001-two-source-rule.md) | Two-Source Rule | Accepted |
| [ADR-002](./ADR-002-gate-ordering.md) | Gate Ordering | Accepted |
| [ADR-003](./ADR-003-tier-system.md) | Tier Classification System | Accepted |
| [ADR-004](./ADR-004-hybrid-verification.md) | Hybrid Event Verification | Accepted |
