# ADR-007: Breaking News Fast-Path

## Status
Accepted

## Context

The standard verification pipeline processes all events through multiple gates (Gate 0-3), taking 30-45 seconds per event. For breaking news from highly credible sources, this delay is unacceptable:

- Wire services (Reuters, AP, AFP) publish verified content
- Readers expect immediate updates on major events
- Competitors publish breaking news instantly
- Delay reduces relevance and user trust

We needed a mechanism to accelerate publication for breaking news from trusted sources while maintaining accuracy.

## Decision

Implement a Breaking News Fast-Path with five detection signals and gate-skipping for Tier-1/2 sources.

### Detection Signals

| Signal | Confidence Boost | Trigger |
|--------|------------------|---------|
| Breaking keywords | +0.4 | "breaking", "urgent", "flash", "alert" |
| Flash patterns | +0.3 | `FLASH:`, `URGENT:`, `BREAKING:` regex |
| Urgent events | +0.2 | Terror attack, invasion, mass casualty |
| Tier-1 source | +0.2 | Reuters, AP, AFP domain |
| Volume spike | +0.3 | 3x normal mention volume |

**Breaking threshold:** Combined confidence ≥ 0.6

### Gate Skipping Rules

| Condition | Gates Skipped |
|-----------|---------------|
| High confidence (≥0.8) + Tier-1/2 | Gate 0, Gate 2, Gate 3 |
| Standard confidence (0.6-0.79) + Tier-1/2 | Gate 2, Gate 3 |
| Non-Tier-1/2 source | No gates skipped |

### Verification Labels

| Label | Confidence | Re-verification Schedule |
|-------|------------|--------------------------|
| FLASH | Any + Flash pattern | 15 minutes |
| BREAKING | ≥0.8 | 20 minutes |
| DEVELOPING | 0.6-0.79 | 30 minutes |

### Compensatory Measures

1. **Label transparency**: Article marked as "DEVELOPING" or "BREAKING"
2. **Scheduled re-verification**: Automatic verification at intervals
3. **Gate 1 required**: Checkworthiness gate never skipped
4. **Source tier requirement**: Only Tier-1/2 sources eligible

## Consequences

### Positive
- Breaking news latency reduced from 45s to 5s (-89%)
- Wire service exclusives published immediately
- Maintained accuracy through source tier requirements
- User trust improved with labeled developing stories
- Compensatory re-verification ensures eventual accuracy

### Negative
- Potential for errors in initial publication
- "DEVELOPING" label may reduce perceived credibility
- Re-verification creates additional processing load
- Complex logic for gate skipping
- Risk of false positives from volume spikes

## Alternatives Considered

### Alternative A: No Fast-Path
Process all events through full pipeline regardless of source.

**Rejected because:**
- Unacceptable latency for breaking news
- Wire services already verified content
- Competitive disadvantage

### Alternative B: Tier-1 Always Skip All Gates
Automatically skip all gates for any Tier-1 source.

**Rejected because:**
- Not all Tier-1 content is breaking news
- Would publish routine updates without verification
- No distinction for urgency level

### Alternative C: Human-in-the-Loop for Breaking
Require human approval for breaking news fast-path.

**Rejected because:**
- Adds latency (defeats purpose)
- Not scalable
- 24/7 coverage required

## Implementation

```python
# Detection
def detect_breaking_news(event: TriggerEvent) -> BreakingResult:
    confidence = 0.0

    if has_breaking_keywords(event.title):
        confidence += 0.4

    if matches_flash_pattern(event.title):
        confidence += 0.3

    if is_urgent_event_type(event.content):
        confidence += 0.2

    if get_domain_tier(event.url) == DomainTier.TIER_1:
        confidence += 0.2

    if detector.is_volume_spike(event.topic):
        confidence += 0.3

    return BreakingResult(
        is_breaking=confidence >= 0.6,
        confidence=confidence,
        fast_path_eligible=get_domain_tier(event.url) in [DomainTier.TIER_1, DomainTier.TIER_2]
    )

# Gate skipping
def get_gates_to_skip(breaking_result: BreakingResult) -> list[str]:
    if not breaking_result.fast_path_eligible:
        return []

    if breaking_result.confidence >= 0.8:
        return ["gate0_verification", "gate2_specificity", "gate3_evidence"]
    else:
        return ["gate2_specificity", "gate3_evidence"]
```

## References
- Implementation: `app/agent/breaking_news.py`
- Scanner integration: `app/agent/scanner.py`
- Source tiers: `app/agent/source_tiers.py`
- ADR-011: Domain Tiers
