# ADR-001: Two-Source Rule

## Status
Accepted

## Context

News verification systems face a critical challenge: balancing publication speed with accuracy. Single-source reports can be:
- Inaccurate or misleading
- Taken out of context
- Deliberately false (misinformation)
- Incomplete or preliminary

The journalism industry has long used the "Two-Source Rule" as a standard practice: before publishing a claim, it should be independently verified by at least two sources.

We needed a systematic approach to ensure our automated system maintains journalistic integrity while processing high volumes of real-time news.

## Decision

Implement the Two-Source Rule as a core verification principle:

### Primary Rule
Events must be verified by at least **2 independent sources** before publication.

### Exception for Tier-1 Government Sources
Single Tier-1 government sources (USGS, NOAA) are sufficient because:
- They are official primary data sources
- Their data is authoritative by definition
- Waiting for cross-verification would delay critical alerts (earthquakes, severe weather)

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
- Single source (non-govt): Base score 0.50 (not publishable)
- Two sources: Base score 0.70 (publishable)
- Three+ sources: Base score 0.85 (high confidence)

## Consequences

### Positive
- Significantly reduces false positive rate
- Aligns with established journalism standards
- Builds user trust through consistent accuracy
- Government data bypass prevents critical delays
- Clear, auditable verification criteria

### Negative
- Some real events may be delayed until cross-verified
- Single-source breaking news cannot be published immediately
- Requires effective cross-source matching algorithm
- May miss events only reported by one source

## Alternatives Considered

### Alternative A: Single Source with High Confidence Threshold
Publish from single sources if confidence score exceeds 0.90.

**Rejected because:**
- Confidence scoring alone cannot guarantee accuracy
- High-tier sources can still report inaccurately
- No independent verification mechanism

### Alternative B: LLM-Based Verification Only
Use LLM to assess truthfulness of single-source reports.

**Rejected because:**
- LLMs can hallucinate or be fooled
- No grounding in real-world verification
- Expensive at scale ($0.001+ per verification)
- Adds latency without true verification

### Alternative C: Time-Based Publication
Publish after N minutes if no contradicting sources found.

**Rejected because:**
- Absence of contradiction is not verification
- Arbitrary time threshold
- Could publish misinformation if sources are slow

## References
- [Two-Source Rule in Journalism](https://en.wikipedia.org/wiki/Confirmation_by_two_sources)
- Project docs: `docs/concepts/README.md`
- Implementation: `app/agent/confidence_scorer.py`
