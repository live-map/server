# Two-Source Rule

The Two-Source Rule is a fundamental journalism principle that LiveMap implements to ensure accuracy.

---

## Definition

> Events require verification from **2 or more independent sources** before publication.

This is a standard practice in professional journalism, used by major news organizations including AP, Reuters, and BBC.

---

## Why Two Sources?

### The Problem with Single Sources

| Scenario | Risk |
|----------|------|
| Source error | Factual mistakes propagate |
| Source bias | One-sided perspective |
| Deliberate misinformation | Unchecked false claims |
| Misinterpretation | Context lost |

### Benefits of Multi-Source Verification

1. **Error detection**: Different sources catch different mistakes
2. **Bias mitigation**: Multiple perspectives balance coverage
3. **Confidence building**: Agreement increases reliability
4. **Context enrichment**: Different angles provide fuller picture

---

## Implementation in LiveMap

### Source Independence

For sources to be considered "independent":

- Different organizations
- Different primary data sources
- No shared ownership or editorial control

**Independent**:
- GDELT (from Reuters) + Reddit (user report) ✓
- USGS + NOAA (different agencies) ✓

**Not independent**:
- Two articles from the same news outlet ✗
- GDELT article and its Reddit share ✗

### Exceptions

| Source Type | Single-Source Publish? | Rationale |
|-------------|------------------------|-----------|
| **Tier-1 Government** (USGS, NOAA) | Yes | Official authoritative data |
| **Tier-1 News** (GDELT) with confidence ≥ 0.70 | Yes | Established editorial standards |
| All other sources | No | Requires corroboration |

### Confidence Scoring Impact

```python
# Two-source satisfied
base_score = 0.70  # vs 0.50 for single source

# Example: GDELT + Reddit
sources = ["gdelt", "reddit"]
base_score = 0.70  # 2 sources
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = 0.03  # Different tiers

final_score = (0.70 * 0.5) + (0.65 * 0.5) + 0.03 = 0.71
```

---

## IFCN Standard

The Two-Source Rule aligns with the International Fact-Checking Network (IFCN) principles:

> "A commitment to nonpartisanship and fairness requires that fact-checkers not rely on a single source for claims of fact."

---

## Examples

### Two-Source Satisfied

```
Event: "Iran launches missiles at US bases in Iraq"

Source 1: GDELT (AP article)
  - "Iran fires ballistic missiles at US forces"
  - Credibility: 0.90

Source 2: Reddit (r/worldnews)
  - "Multiple reports of missile attacks on US bases"
  - Credibility: 0.40

Result: Two-Source Rule satisfied
Recommendation: Publishable
```

### Single Source (Not Published)

```
Event: "UFO spotted over Pentagon"

Source 1: Reddit (r/conspiracy)
  - User report with photo
  - Credibility: 0.40

Result: Two-Source Rule NOT satisfied
Recommendation: Do not publish (await corroboration)
```

### Tier-1 Government Exception

```
Event: "M6.2 earthquake in Alaska"

Source: USGS (official)
  - Official seismograph data
  - Credibility: 0.99

Result: Two-Source Rule EXEMPTED
Recommendation: Immediate publish
```

---

## Configuration

```python
# config.py
class AgentSettings:
    # Two-Source Rule
    require_two_sources: bool = True

    # Exceptions
    tier1_govt_immediate_publish: bool = True
    tier1_news_min_confidence: float = 0.70
```

---

## Related Documentation

- [Source Tiers](SOURCE_TIERS.md) - How sources are classified
- [Confidence Scoring](CONFIDENCE_SCORING.md) - How scores are calculated
- [ADR-001: Two-Source Rule](../adr/ADR-001-two-source-rule.md) - Design decision
