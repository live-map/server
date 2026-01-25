# Phase 7: Zero-Shot ML Classification

**Date**: January 23, 2026

---

## Overview

BART-MNLI 모델을 사용한 zero-shot 분류를 추가하여 이벤트 검증을 수행하고, 총 LLM 비용을 91% 절감했습니다.

---

## Problem Statement

규칙 기반 필터링(Phase 4)을 적용한 후에도 너무 많은 이벤트가 비용이 높은 LLM 검증으로 전달되고 있었습니다:

| Stage | Events | Cost |
|-------|--------|------|
| Input | 168 | - |
| After Rules | 50 | $0 |
| LLM Verification | 50 | $4.80/day |

**Goal**: 정확도를 유지하면서 LLM 호출을 줄입니다.

---

## Solution: 3-Stage Hybrid Pipeline

```
Stage 1: Rules ($0)     ──► ~70% filtered
Stage 2: Zero-shot ($0) ──► ~70% of remaining decided
Stage 3: LLM ($0.001)   ──► Edge cases only (~15 events)
```

### Stage 2: Zero-Shot Classification

zero-shot 분류를 위해 `facebook/bart-large-mnli`를 사용합니다:

```python
from transformers import pipeline

classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

# CAMEO/ACLED-based labels
INTERNATIONAL_LABELS = [
    "military conflict",
    "diplomatic relations",
    "terrorism",
    "humanitarian crisis",
]

REJECT_LABELS = [
    "sports",
    "entertainment",
    "local news",
]
```

### Decision Logic

| Classification | Confidence | Action |
|----------------|------------|--------|
| International | ≥ 0.8 | 즉시 PASS |
| Rejection | ≥ 0.8 | 즉시 REJECT |
| Any | < 0.8 | LLM으로 전달 |

---

## Implementation

### Zero-Shot Classifier Module

```python
# app/agent/zero_shot_classifier.py
class ZeroShotEventClassifier:
    def __init__(self):
        self.classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli"
        )

    def classify(self, text: str) -> tuple[bool | None, float, str]:
        """
        Returns: (is_international, confidence, label)
        """
        all_labels = INTERNATIONAL_LABELS + REJECT_LABELS
        result = self.classifier(text, all_labels)

        top_label = result["labels"][0]
        confidence = result["scores"][0]

        if top_label in INTERNATIONAL_LABELS:
            return True, confidence, top_label
        else:
            return False, confidence, top_label
```

### Integration with Event Verifier

```python
async def verify_event_hybrid(text: str, ...) -> tuple[bool, str]:
    # Stage 1: Rules
    passed_rules, reason = is_likely_real_event(text)
    if not passed_rules:
        return False, reason

    # Stage 2: Zero-shot
    is_intl, confidence, label = classify_with_zero_shot(text)
    if confidence >= 0.8:
        if is_intl:
            return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
        else:
            return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM (uncertain cases)
    return await verify_event_with_llm(text, llm)
```

---

## Cost Analysis

### Before (2-Stage: Rules + LLM)

| Stage | Events | Cost |
|-------|--------|------|
| Rules | 168 → 50 | $0 |
| LLM | 50 all | $0.05/scan |
| **Daily** | | **$4.80** |

### After (3-Stage: Rules + Zero-shot + LLM)

| Stage | Events | Cost |
|-------|--------|------|
| Rules | 168 → 50 | $0 |
| Zero-shot | 50 → 15 LLM | $0 |
| LLM | 15 only | $0.015/scan |
| **Daily** | | **$1.44** |

**Result**: 70% 절감 (LLM 전용 기준 대비 총 91% 절감)

---

## Performance

| Metric | Value |
|--------|-------|
| Zero-shot latency | ~50ms/event |
| Model size | ~1.6GB |
| First load time | ~30s |
| Accuracy | ~90% |

---

## Configuration

```python
# config.py
event_verification_enabled: bool = True
event_verification_use_zero_shot: bool = True
event_verification_use_llm: bool = True
```

---

## Lessons Learned

1. **Local ML is viable**: BART-MNLI는 CPU에서 효율적으로 실행됩니다
2. **Confidence thresholds matter**: 0.8은 정확도와 비용 사이의 균형을 맞춥니다
3. **Hybrid beats single approach**: 각 단계가 서로 다른 패턴을 필터링합니다

---

## Related Documentation

- [Zero-Shot Classifier](../architecture/ZERO_SHOT_CLASSIFIER.md) - 기술 세부사항
- [Event Verification](../architecture/EVENT_VERIFICATION.md) - 전체 Gate 0 문서
- [ADR-004: Hybrid Verification](../adr/ADR-004-hybrid-verification.md) - 결정 기록
