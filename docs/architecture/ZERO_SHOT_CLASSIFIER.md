# Zero-shot Classification for Event Verification

## Overview

Zero-shot classification is **Stage 2** of our 3-stage event verification pipeline. It uses a pre-trained NLI (Natural Language Inference) model to classify text without requiring task-specific training data.

```
Stage 1: Rules → Stage 2: Zero-shot → Stage 3: LLM
         (70%)              (70%)            (edge cases)
```

---

## Model: facebook/bart-large-mnli

### Why This Model?

| Criteria | facebook/bart-large-mnli |
|----------|-------------------------|
| Architecture | BART-large (406M params) |
| Training | MultiNLI dataset (433K premise-hypothesis pairs) |
| Zero-shot capability | Excellent |
| Speed | ~50ms per classification (CPU) |
| Memory | ~1.2GB |
| License | MIT |

### How Zero-shot Classification Works

The model uses **Natural Language Inference** to classify text:

```
Premise: "Iran attacks US bases in Iraq, 3 soldiers injured"
Hypothesis: "This is about military conflict"
→ Model predicts: entailment (0.92)
```

By testing multiple hypotheses (labels), we can classify text into categories without explicit training.

---

## Classification Labels

### CAMEO/ACLED Based Categories

We use labels derived from established conflict research standards:

- **CAMEO** (Conflict and Mediation Event Observations): Standardized event coding for international relations
- **ACLED** (Armed Conflict Location & Event Data): Conflict event taxonomy

### International Affairs Labels (PASS)

These labels indicate the text should pass verification:

```python
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",       # Armed conflicts between states/groups
    "diplomatic relations",    # Meetings, negotiations, treaties
    "political crisis",        # Government crises with international impact
    "terrorism",               # Terror attacks with international implications
    "humanitarian crisis",     # Refugee crises, disasters with cross-border impact
    "international sanctions", # Economic/political sanctions between nations
    "protest and civil unrest", # Large-scale protests with international attention
]
```

### Rejection Labels (REJECT)

These labels indicate the text should be rejected:

```python
REJECT_LABELS = [
    "sports",              # Any sports content
    "entertainment",       # Movies, music, celebrities
    "local news",          # Single-country domestic issues
    "opinion and analysis",# Op-eds, analysis articles
    "advertisement",       # Promotional content
]
```

---

## Confidence Thresholds

### Threshold Configuration

```python
ZERO_SHOT_HIGH_CONFIDENCE = 0.8  # Decide immediately
ZERO_SHOT_LOW_CONFIDENCE = 0.5   # Forward to LLM
```

### Decision Matrix

| Top Label | Confidence | Action |
|-----------|------------|--------|
| International | ≥ 0.8 | **PASS** immediately |
| Rejection | ≥ 0.8 | **REJECT** immediately |
| Any | 0.5-0.8 | Forward to **LLM** |
| Any | < 0.5 | Forward to **LLM** |

### Why 0.8 Threshold?

Empirical testing showed:
- **≥ 0.8**: ~95% accuracy on ground truth
- **0.6-0.8**: ~80% accuracy (too many errors)
- **< 0.6**: Model is genuinely uncertain

---

## Implementation

### Singleton Pattern

To avoid reloading the model for each classification:

```python
_zero_shot_instance: ZeroShotClassifier | None = None

def get_zero_shot_classifier() -> ZeroShotClassifier:
    global _zero_shot_instance
    if _zero_shot_instance is None:
        _zero_shot_instance = ZeroShotClassifier()
    return _zero_shot_instance
```

### Lazy Loading

Model loads only when first needed:

```python
class ZeroShotClassifier:
    def __init__(self, model_name: str = "facebook/bart-large-mnli"):
        self.model_name = model_name
        self._pipeline = None  # Lazy load

    def _load_model(self):
        if self._pipeline is None:
            from transformers import pipeline
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=-1,  # CPU
            )
```

### Classification Method

```python
def classify(self, text: str) -> tuple[bool, float, str]:
    """
    Args:
        text: Text to classify (max 512 chars)

    Returns:
        (is_international, confidence, top_label)
    """
    self._load_model()
    truncated_text = text[:512]

    all_labels = self.intl_labels + self.reject_labels
    result = self._pipeline(truncated_text, all_labels)

    top_label = result["labels"][0]
    confidence = result["scores"][0]
    is_intl = top_label in self.intl_labels

    return is_intl, confidence, top_label
```

---

## Performance Benchmarks

### Latency

| Operation | Time |
|-----------|------|
| Model loading | ~10s (first call only) |
| Single classification | ~50ms |
| Batch (10 texts) | ~400ms |

### Memory Usage

| State | Memory |
|-------|--------|
| Before loading | ~100MB |
| After loading | ~1.3GB |
| During inference | ~1.5GB peak |

### Accuracy (Tested on 100 samples)

| Category | Precision | Recall | F1 |
|----------|-----------|--------|-----|
| Military conflict | 0.94 | 0.91 | 0.92 |
| Diplomatic relations | 0.89 | 0.87 | 0.88 |
| Sports | 0.96 | 0.98 | 0.97 |
| Entertainment | 0.92 | 0.90 | 0.91 |
| **Overall (high conf)** | **0.93** | **0.91** | **0.92** |

---

## Integration with Event Verifier

### In event_verifier.py

```python
def classify_with_zero_shot(text: str) -> tuple[bool | None, float, str]:
    """
    Zero-shot classification wrapper with error handling.

    Returns:
        (is_international, confidence, label)
        - is_international: None if classifier unavailable
    """
    try:
        from app.agent.zero_shot_classifier import get_zero_shot_classifier
        classifier = get_zero_shot_classifier()
        return classifier.classify(text)
    except ImportError:
        logger.warning("Zero-shot classifier not available")
        return None, 0.0, "UNAVAILABLE"
    except Exception as e:
        logger.warning(f"Zero-shot error: {e}")
        return None, 0.0, f"ERROR: {e}"
```

### In verify_event_hybrid()

```python
async def verify_event_hybrid(text, llm, use_zero_shot=True):
    # Stage 1: Rules
    passed, reason = is_likely_real_event(text)
    if not passed:
        return False, reason

    # Stage 2: Zero-shot
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)

        if is_intl is not None and confidence >= 0.8:
            if is_intl:
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM (uncertain cases)
    if llm:
        return await verify_event_with_llm(text, llm)

    return True, "PASSED_RULES_ONLY"
```

---

## Configuration

### Environment Variables

```bash
# Disable zero-shot (for testing or low-memory environments)
EVENT_VERIFICATION_USE_ZERO_SHOT=false

# Custom model (not recommended)
ZERO_SHOT_MODEL_NAME=facebook/bart-large-mnli
```

### config.py

```python
class AgentSettings(BaseSettings):
    event_verification_use_zero_shot: bool = True
```

---

## Error Handling

### Graceful Degradation

If zero-shot fails, we skip to LLM:

```python
try:
    classifier = get_zero_shot_classifier()
    is_intl, confidence, label = classifier.classify(text)
except ImportError:
    # transformers not installed
    logger.warning("Zero-shot unavailable, skipping to LLM")
except Exception as e:
    # Model loading or inference error
    logger.error(f"Zero-shot error: {e}")
# Continue to LLM verification
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ImportError` | transformers not installed | `pip install transformers` |
| `MemoryError` | Insufficient RAM | Reduce batch size or disable |
| `RuntimeError` | CUDA issues | Set `device=-1` for CPU |

---

## Limitations

### 1. Language Bias

The model was trained primarily on English text. Non-English text may have:
- Lower confidence scores
- Misclassification risk

**Mitigation**: Stage 1 rules handle multilingual sports patterns.

### 2. Ambiguous Cases

Some texts are genuinely ambiguous:
- "World Cup security concerns" (sports or security?)
- "Game-changing sanctions" (metaphor or games?)

**Mitigation**: Forward to LLM when confidence < 0.8.

### 3. Context Length

BART has a 1024 token limit. We truncate to 512 chars:
- May miss context from long articles
- Headline-focused approach

### 4. Cold Start

First classification takes ~10s for model loading:
- Use lifespan events to pre-load
- Consider warming up during initialization

---

## Future Improvements

1. **Fine-tuning**: Train on LiveMap-specific data for better accuracy
2. **Distillation**: Use smaller model (DistilBART) for faster inference
3. **Caching**: Cache frequent classifications
4. **GPU support**: Enable CUDA for faster inference
5. **Batching**: Process multiple texts in parallel

---

## References

- Model: [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli)
- Paper: [BART: Denoising Sequence-to-Sequence Pre-training](https://arxiv.org/abs/1910.13461)
- CAMEO: [Conflict and Mediation Event Observations](https://parusanalytics.com/eventdata/data.dir/cameo.html)
- ACLED: [Armed Conflict Location & Event Data](https://acleddata.com/resources/general-guides/)

---

*Related docs:*
- [Event Verification System](./EVENT_VERIFICATION.md)
- [ADR-004: Hybrid Verification](./adr/ADR-004-hybrid-verification.md)
