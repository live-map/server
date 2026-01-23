# ADR-002: Gate Ordering

## Status
Accepted

## Context

The scanner pipeline processes raw events through multiple filtering stages (gates). Each gate has different:
- **Cost**: CPU time, LLM API calls, database queries
- **Filtering power**: Percentage of events rejected
- **Dependencies**: Some gates require prior processing results

We needed to determine the optimal order to:
1. Minimize processing costs
2. Maximize filtering efficiency
3. Maintain logical data flow

## Decision

Implement gates in the following order:

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
| 0 | Hybrid | Low-Medium | ~70% | Real event vs non-event |
| 1 | Pattern | Very Low | ~15% | Newsworthy vs entertainment |
| 2 | Pattern | Very Low | ~10% | Specific vs vague |
| 3 | LLM | High | ~5% | Evidence verification |

### Rationale for Ordering

1. **Gate 0 first (Event Verification)**
   - Rules filter 70% for free ($0)
   - Only 30% need LLM verification ($0.001/event)
   - Removes non-events before expensive processing

2. **Gate 1 second (Check-worthiness)**
   - Pure pattern matching (microseconds)
   - Removes entertainment/speculation quickly
   - Reduces load on subsequent gates

3. **Gate 2 third (Specificity)**
   - Pattern-based (microseconds)
   - English-only patterns (skip non-English)
   - Further reduces candidate set

4. **Gate 3 last (Evidence)**
   - Most expensive (LLM-based)
   - Only processes verified, newsworthy, specific events
   - Applied to smallest possible set

## Consequences

### Positive
- Cost-efficient: Cheapest filters first
- Fast rejection: Most events rejected quickly
- Resource optimization: Expensive operations minimized
- Clear logical flow: Each gate builds on previous
- Easy debugging: Failures traceable to specific gate

### Negative
- Tier-1 govt sources bypass some gates (necessary trade-off)
- Non-English content skips Gate 2 (pattern limitation)
- Gate ordering is tightly coupled
- Changing order requires careful analysis

## Alternatives Considered

### Alternative A: Parallel Gate Processing
Run all gates simultaneously and combine results.

**Rejected because:**
- Wastes resources processing events that would fail early gates
- More complex result merging logic
- No cost reduction benefit
- Harder to debug filtering decisions

### Alternative B: ML-Based Single Gate
Train a single ML model to filter all unwanted content.

**Rejected because:**
- Black-box decision making
- Expensive training and inference
- Harder to explain rejections
- Single point of failure

### Alternative C: Reverse Order (Expensive First)
Run evidence verification before pattern matching.

**Rejected because:**
- 10x higher API costs
- Slower overall processing
- No logical benefit
- Wastes LLM calls on entertainment content

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
- Implementation: `app/agent/scanner.py:_classify_and_group()`
- Gate 0: `app/agent/event_verifier.py`
- Gate 1: `app/agent/checkworthiness.py`
- Gate 2: `app/agent/specificity.py`
