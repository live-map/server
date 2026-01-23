# ADR-004: Hybrid Event Verification

## Status
Accepted

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

Implement a **hybrid two-stage verification system**:

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
    r"\b(world war (i|ii|1|2))\s+(?!fears|concerns)",

    # Hypothetical
    r"\b(if .* would|could potentially|might happen)\b",
    r"\b(what if|scenario|simulation|prediction)\b",

    # Sports
    r"\b(football|soccer|basketball|baseball|tennis)\b",
    r"\b(world cup|championship|tournament|playoffs)\b",
    # ...
]
```

**Expected filtering**: ~70% of non-events

### Stage 2: LLM Verification (Paid, Accurate)
For events passing rules, use LLM to verify:

```python
PROMPT = """
Is this text reporting a real, recent international event?

YES: Real event (war, diplomacy, disaster, protest)
NO: Entertainment, history, speculation, sports, fiction

Text: {text}
Answer: VERDICT: YES/NO, REASON: ...
"""
```

**Cost**: ~$0.001 per verification (GPT-4o-mini)

### Architecture Flow

```
Input Events (100%)
    ↓
Stage 1: Rules (~70% rejected, $0)
    ↓
Remaining Events (~30%)
    ↓
Stage 2: LLM (~10% rejected, $0.001/event)
    ↓
Verified Events (~27%)
```

### Error Handling
- LLM timeout: Pass (false positive better than false negative)
- LLM error: Pass and log
- Rule error: Log and continue

## Consequences

### Positive
- **Cost-efficient**: 70% filtered for free
- **Accurate**: LLM catches sophisticated false positives
- **Fast**: Rules execute in microseconds
- **Graceful degradation**: Works without LLM (rules only)
- **Transparent**: Rejection reasons are logged

### Negative
- Rules require maintenance as patterns evolve
- English-centric patterns (non-English may have lower rule filtering)
- LLM adds 100-500ms latency
- LLM costs scale with event volume
- Dual system more complex than single approach

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

**Rejected because:**
- Requires labeled training data
- Model maintenance overhead
- May not generalize to new patterns
- Less interpretable than rules

## Performance Characteristics

| Metric | Stage 1 (Rules) | Stage 2 (LLM) |
|--------|-----------------|---------------|
| Latency | ~1ms | ~300ms |
| Cost | $0 | $0.001/event |
| Accuracy | ~85% | ~95% |
| Filter Rate | ~70% | ~10% of remaining |

## Implementation

```python
async def verify_event_hybrid(
    text: str,
    llm: ChatOpenAI | None = None,
    use_llm: bool = True
) -> tuple[bool, str]:
    # Stage 1: Rules
    passed_rules, rejection = is_likely_real_event(text)
    if not passed_rules:
        return False, rejection

    # Stage 2: LLM (if enabled)
    if use_llm and llm:
        return await verify_event_with_llm(text, llm)

    return True, "PASSED_RULES_ONLY"
```

## References
- Implementation: `app/agent/event_verifier.py`
- Gate ordering: `docs/adr/ADR-002-gate-ordering.md`
- Project docs: `docs/EVENT_VERIFICATION.md`
