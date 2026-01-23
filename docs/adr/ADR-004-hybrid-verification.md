# ADR-004: Hybrid Event Verification (v2)

## Status
Accepted (v2 - Updated 2025-01-23)

> **History**: Original ADR-004 described a 2-stage system (Rules → LLM). This v2 adds Zero-shot classification as Stage 2.

## Context

Keyword-based news collection has a fundamental problem: **high false positive rate**. When searching for keywords like "attack," "missile," or "war," we collect:
- Movie reviews ("New war movie releases")
- Video game updates ("Call of Duty attack mode")
- Historical content ("In 1945, the war ended")
- Speculation ("If Russia attacks, NATO might...")
- Sports ("France attacks Argentina's defense")

Initial estimates showed 60-70% of collected content was not actual news events.

We needed an efficient way to filter non-events while:
1. Keeping costs low
2. Maintaining high accuracy
3. Minimizing latency

## Decision

Implement a **hybrid three-stage verification system**:

### Stage 1: Rule-Based Filter (Free, Fast)

Pattern matching to reject obvious non-events:

```python
NOT_EVENT_PATTERNS = [
    # Entertainment
    r"\b(movie|film|tv show|series|drama|actor|actress)\b",
    r"\b(box office|premiere|trailer|sequel|franchise)\b",

    # Games
    r"\b(video game|gaming|esports|playstation|xbox)\b",
    r"\b(call of duty|fortnite|minecraft)\b",

    # History
    r"\b(in \d{4}|years ago|historically|decades ago)\b",
    r"\b(world war (i|ii|1|2))\s+(?!fears|concerns|tensions)",

    # Hypothetical
    r"\b(if .* would|could potentially|might happen)\b",
    r"\b(what if|scenario|simulation|prediction)\b",

    # Sports (English + Multilingual)
    r"\b(football|soccer|basketball|baseball|tennis)\b",
    r"\b(world cup|championship|tournament|playoffs)\b",
    r"(손흥민|황희찬|이강인)",  # Korean sports figures
    r"(皇马|巴萨|曼联)",  # Chinese sports teams
    r"(ريال مدريد|برشلونة)",  # Arabic sports teams
    # ...
]
```

**Expected filtering**: ~70% of non-events

### Stage 2: Zero-shot Classification (Free, Fast)

**New in v2**: Local ML model for classification before LLM.

```python
# Using facebook/bart-large-mnli
from transformers import pipeline

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Classification labels (CAMEO/ACLED based)
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",
    "diplomatic relations",
    "political crisis",
    "terrorism",
    "humanitarian crisis",
    "international sanctions",
    "protest and civil unrest",
]

REJECT_LABELS = [
    "sports",
    "entertainment",
    "local news",
    "opinion and analysis",
    "advertisement",
]
```

**Confidence thresholds**:
- ≥ 0.8: Decide immediately (PASS or REJECT)
- < 0.8: Forward to LLM (Stage 3)

**Expected outcome**: ~70% of remaining events decided without LLM

### Stage 3: LLM Verification (Paid, Accurate)

For events where Zero-shot is uncertain, use LLM to verify:

```python
PROMPT = """Today's date: {today}

## Task
Determine if this text reports an INTERNATIONAL AFFAIRS event.

## Definition
International affairs = events involving 2+ countries OR global security implications.

## Classification
PASS if ANY of these:
- Military conflict between nations
- Diplomatic meeting/negotiation between countries
- International sanctions, treaties, agreements
- UN/NATO/international organization actions
- Cross-border humanitarian crisis

REJECT if ANY of these:
- Single country domestic politics
- Sports (any language)
- Entertainment, celebrities
- Opinion/analysis articles

Text: {text}

## Output
VERDICT: PASS or REJECT
REASON: brief explanation
"""
```

**Cost**: ~$0.001 per verification (GPT-4o-mini)

### Architecture Flow

```
Input Events (100%)
    ↓
Stage 1: Rules (~70% rejected, $0, ~1ms)
    ↓
Remaining Events (~30%)
    ↓
Stage 2: Zero-shot (~70% decided, $0, ~50ms)
    ↓
Uncertain Events (~9%)
    ↓
Stage 3: LLM (~10% rejected, $0.001/event, ~300ms)
    ↓
Verified Events (~20%)
```

### Error Handling (Updated in v2)

- **Stage 2 failure**: Skip to Stage 3 (graceful degradation)
- **Stage 3 timeout**: Reject (conservative approach)
- **Stage 3 error**: Reject and log
- **Rule error**: Log and continue

> **Change from v1**: LLM errors now result in rejection (conservative) instead of pass (permissive).

## Consequences

### Positive
- **Cost-efficient**: 90% filtered without LLM calls
- **Accurate**: Three-layer filtering catches sophisticated false positives
- **Fast**: Rules execute in microseconds, Zero-shot in ~50ms
- **Graceful degradation**: Works without Zero-shot or LLM
- **Transparent**: Rejection reasons are logged at each stage
- **Multilingual**: Supports Korean, Chinese, Arabic sports patterns

### Negative
- Rules require maintenance as patterns evolve
- Zero-shot model requires ~1.2GB memory
- Initial model loading adds ~10s startup time
- Three-stage system more complex than single approach
- Zero-shot accuracy varies by domain

## Alternatives Considered

### Alternative A: LLM-Only Verification
Use LLM for all verification.

**Rejected because:**
- 10x higher cost ($0.01 per event)
- Higher latency for all events
- Single point of failure
- Overkill for obvious cases

### Alternative B: Rules-Only Verification
Use only pattern matching.

**Rejected because:**
- Can't catch sophisticated false positives
- Pattern maintenance burden grows
- Lower accuracy on edge cases
- No semantic understanding

### Alternative C: ML Classification Model
Train custom classifier for event detection.

**Partially adopted as Stage 2** using zero-shot classification instead of custom training:
- No labeled training data required
- Pre-trained model generalizes well
- Interpretable labels from CAMEO/ACLED standards

## Performance Characteristics

| Metric | Stage 1 (Rules) | Stage 2 (Zero-shot) | Stage 3 (LLM) |
|--------|-----------------|---------------------|---------------|
| Latency | ~1ms | ~50ms | ~300ms |
| Cost | $0 | $0 | $0.001/event |
| Accuracy | ~85% | ~90% | ~95% |
| Filter Rate | ~70% | ~70% of remaining | ~10% of remaining |

### Cost Comparison

| Approach | Cost/day (168 events × 96 scans) |
|----------|----------------------------------|
| LLM-only | $16.13 |
| 2-stage (v1) | $4.80 |
| 3-stage (v2) | **$1.44** |

## Implementation

```python
async def verify_event_hybrid(
    text: str,
    llm: ChatOpenAI | None = None,
    use_llm: bool = True,
    use_zero_shot: bool = True
) -> tuple[bool, str]:
    # Stage 1: Rules
    passed_rules, rejection = is_likely_real_event(text)
    if not passed_rules:
        return False, rejection

    # Stage 2: Zero-shot (if enabled)
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)
        if is_intl is not None and confidence >= 0.8:
            if is_intl:
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM (if enabled and needed)
    if use_llm and llm:
        try:
            return await verify_event_with_llm(text, llm)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return False, "LLM_ERROR: verification failed"

    return True, "PASSED_RULES_ONLY"
```

## References
- Implementation: `app/agent/event_verifier.py`
- Zero-shot classifier: `app/agent/zero_shot_classifier.py`
- Gate ordering: `docs/adr/ADR-002-gate-ordering.md`
- Project docs: `docs/EVENT_VERIFICATION.md`
- Zero-shot docs: `docs/architecture/ZERO_SHOT_CLASSIFIER.md`

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-23 | v1 | Initial 2-stage hybrid (Rules → LLM) |
| 2025-01-23 | v2 | Added Zero-shot classification (Stage 2), changed LLM error handling to conservative |
