# Investigation Agent Architecture Comparison

> Test Date: 2026-01-13
> Test Query: "Protests in Iran against government January 2026"
> Category: protest

---

## Executive Summary

| Metric | 방안 B (Parallel Research) | 방안 C (Deep Verification) |
|--------|----------------------------|----------------------------|
| **Execution Time** | 34.8 sec | 62.0 sec |
| **Sources Collected** | 60 (15 unique) | 45 (15 unique) |
| **Verified Facts** | 4 | 5 |
| **Timeline Items** | 18 | 18 |
| **Summary Length** | 416 chars | 562 chars |
| **Unverified Claims** | 2 | 0 |
| **Disputed Claims** | N/A | 0 |

---

## Architecture Overview

### 방안 B: Parallel Research Agent (GPT-Researcher Style)

```
PLANNER → PARALLEL RESEARCHERS → SUMMARIZER → AGGREGATOR → PUBLISHER
                ↓ (7 parallel)
         [asyncio.gather()]
```

**Key Features:**
- Generates 5-7 targeted research questions
- True parallel execution with `asyncio.gather()`
- Frequency-based consensus (more sources = higher confidence)
- Two modes: LangGraph sequential and true parallel

**Strengths:**
- Fast execution (34.8 sec)
- High source volume (60 collected)
- Frequency-based verification

**Weaknesses:**
- More unverified claims (2)
- Less structured verification
- No explicit conflict detection

### 방안 C: Deep Verification Agent (Perplexity Style)

```
DECOMPOSER → RESEARCHER → NOTER → (loop for each subtopic) → VERIFIER → SYNTHESIZER
```

**Key Features:**
- Query decomposition into 3-5 subtopics
- Sequential multi-pass retrieval per subtopic
- Structured intermediate notes
- Explicit conflict detection and confidence scoring

**Strengths:**
- More verified facts (5)
- Zero unverified claims
- Explicit conflict detection
- Better structured synthesis
- Longer, more detailed summary

**Weaknesses:**
- Slower execution (62.0 sec)
- Sequential subtopic processing
- Higher LLM costs (more synthesis steps)

---

## Detailed Comparison

### 1. Speed vs. Quality Tradeoff

| Approach | Time | Quality Score* |
|----------|------|----------------|
| 방안 B | 34.8s | 80% |
| 방안 C | 62.0s | 90% |

*Quality Score based on: verified facts ratio, summary depth, conflict detection

**Verdict:** 방안 C produces higher quality output at the cost of ~2x execution time.

### 2. Source Coverage

**방안 B:**
- 60 sources collected across 7 parallel researchers
- 15 unique after deduplication
- Focuses on breadth

**방안 C:**
- 45 sources collected across 5 subtopics
- 15 unique after deduplication
- Focuses on depth per subtopic

**Verdict:** Similar final source count, but 방안 B collects more raw data faster.

### 3. Verification Quality

**방안 B:**
- 4 verified facts
- 2 unverified claims
- Uses frequency-based consensus

**방안 C:**
- 5 verified facts
- 0 unverified claims
- Uses explicit cross-verification step

**Verdict:** 방안 C produces cleaner output with better verification.

### 4. Output Quality

**방안 B Summary (416 chars):**
> Protests in Iran have erupted nationwide, initially sparked by widespread outrage over the deteriorating economy. As the demonstrations have escalated, they have resulted in a significant increase in violence, with reports indicating over 540 fatalities...

**방안 C Summary (562 chars):**
> Protests in Iran have erupted in January 2026, primarily driven by economic grievances, and have escalated nationwide, prompting a significant crackdown by authorities. Activists report that the death toll has surpassed 540, reflecting the severe violence and repression faced by demonstrators. In response, the Iranian government has organized a "national resistance march" to rally support for the regime while simultaneously expressing a willingness to engage in discussions...

**Verdict:** 방안 C produces more detailed, nuanced summaries.

---

## Recommendations

### Use Case Selection

| Scenario | Recommended |
|----------|-------------|
| Breaking news (speed critical) | 방안 B |
| In-depth investigation | 방안 C |
| Cost-sensitive deployment | 방안 B |
| High-stakes reporting | 방안 C |
| Real-time alerts | 방안 B |
| Daily digest generation | 방안 C |

### Hybrid Approach (Future)

Consider combining both approaches:
1. Use 방안 B for initial rapid collection
2. Feed results to 방안 C's verification pipeline
3. Best of both worlds: speed + quality

---

## Test Configuration

**Environment:**
- Model: GPT-4o-mini
- Search Tools: GDELT, DuckDuckGo (free), Tavily (paid fallback)
- Date: 2026-01-13

**방안 B Config:**
```python
recursion_limit: 50
max_researchers: 7
```

**방안 C Config:**
```python
recursion_limit: 50
max_subtopics: 5
```

---

## Raw Test Results

### 방안 B Output
- File: `/tmp/parallel_test_result.txt`

### 방안 C Output
- File: `/tmp/deep_verification_simplified.txt`

---

*Generated: 2026-01-13*
*Branch A: feature/parallel-researchers*
*Branch B: feature/deep-verification*
