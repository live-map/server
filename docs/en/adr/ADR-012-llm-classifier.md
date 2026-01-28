# ADR-012: Replace Pattern-Based Filtering with LLM Classifier

## Status
**Accepted** (2026-01-27)

## Context

### Existing System
Pattern-based Gate system for news filtering:
- Gate 0 (Event Verification): ~200 regex patterns
- Gate 1 (Check-worthiness): ~150 regex patterns
- Gate 2 (Specificity): ~100 regex patterns
- Other category patterns: ~150 regex patterns
- **Total 600+ regex patterns**

### Problems

1. **Ignores Context**
   ```
   "Warsaw summit" → matches "war" → Misclassification
   "War movie review" → matches "war" → Misclassification
   ```

2. **Maintenance Difficulty**
   - New patterns conflict with existing ones
   - Need pattern additions for each edge case
   - Increasing code complexity

3. **Multilingual Limitations**
   - Only English patterns exist
   - Need to duplicate pattern sets for new languages

4. **False Positive/Negative**
   - Limitations of simple string matching
   - Cannot understand nuance/context

## Decision

**Replace 600+ regex patterns with a single LLM prompt**

### Chosen Approach
- Deepinfra API + Llama 3.1 8B Instruct
- Single prompt for is_news, category, is_significant, temporal_category
- Batch processing (20 articles/request)

### Alternative Comparison

| Approach | Cost | Accuracy | Maintenance | Selected |
|----------|------|----------|-------------|----------|
| Keep Patterns | $0 | ~85% | High | X |
| **LLM Classification** | $3-7/month | ~95% | Low | **O** |
| ML Model Training | $0 (inference) | ~90% | Medium | X |
| Hybrid | $1-2/month | ~93% | Medium | X |

### Selection Rationale
1. **Cost Efficiency**: Deepinfra Llama 8B is very affordable (~$0.03/1M input)
2. **Accuracy**: Context understanding reduces False Positives
3. **Maintenance**: Edit one prompt line vs. dozens of patterns
4. **Multilingual**: Automatic support (no additional work)

## Implementation

### LLM Classifier (`llm_classifier.py`)

```python
CLASSIFICATION_PROMPT = """
You are a breaking international news classifier.
Today's date: {current_date}

For each article, determine:
1. TEMPORAL_CATEGORY: breaking|developing|retrospective|predictive|timeless
2. IS_NEWS: Is this a real breaking news event?
3. CATEGORY: war|conflict|politics|security|military|terrorism|diplomacy|protest|other
4. IS_SIGNIFICANT: Is this internationally significant?

Return JSON: {
  "temporal_category": str,
  "is_news": bool,
  "category": str,
  "is_significant": bool,
  "temporal_markers_found": list,
  "reason": str
}
"""
```

### Temporal Classification System (Phase 6.1)

| Category | Time Range | Publish | Linguistic Markers |
|----------|-----------|---------|-------------------|
| **BREAKING** | Within 24h | Yes | "just", "breaking", present tense |
| **DEVELOPING** | 1-7 days | Yes | "latest update", "Day N of" |
| **RETROSPECTIVE** | 7+ days | **No** | "years later", "looking back", "analysis" |
| **PREDICTIVE** | Future | **No** | "could", "may", "expected to" |
| **TIMELESS** | Timeless | Evaluate | Encyclopedic content |

### Configuration (`config.py`)

```python
llm_classifier_enabled: bool = True
deepinfra_api_key: str = ""
llm_classifier_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
llm_classifier_batch_size: int = 20
llm_classifier_fallback_enabled: bool = True  # Pattern fallback

# Phase 6.1: Temporal Classification
temporal_classification_enabled: bool = True
temporal_filter_enabled: bool = True
temporal_reject_categories: str = "retrospective,predictive"
```

### Pipeline Integration (`scanner.py`)

```python
# Step 3.35: LLM Classification
if use_llm_classification:
    llm_result = await classify_articles(articles_for_llm)
    # is_news=False → Reject
    # is_significant=False → Reject
    # category=other → Reject
    # temporal_category=retrospective|predictive → Reject (Phase 6.1)
```

## Results

### Expected Effects

| Metric | Before | After |
|--------|--------|-------|
| Pattern Count | 600+ | 1 (prompt) |
| Misclassification Fix Time | Hours | Minutes |
| Multilingual Support | Need patterns | Automatic |
| Monthly Cost | $0 | $5-7 |
| Retrospective Filtering | ~85% | ~95% |

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| API Outage | `llm_classifier_fallback_enabled=True` |
| Hallucination | Enforce JSON structure, confidence threshold |
| Cost Overrun | Batch processing, daily limits |

## Related Documents

- [Phase 6 History](../history/PHASE_6_LLM_CLASSIFIER.md)
- [ADR-004: Hybrid Verification](ADR-004-hybrid-verification.md)
- [Source Tiers](../algorithms/SOURCE_TIERS.md)

## Change History

| Date | Change | Author |
|------|--------|--------|
| 2026-01-27 | Initial draft | Claude |
| 2026-01-27 | Added Temporal Classification (Phase 6.1) | Claude |
