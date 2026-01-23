# Architecture Documentation

This section contains detailed technical documentation for the LiveMap system architecture.

---

## Overview

LiveMap uses a 7-stage pipeline architecture to process news events from collection to publication:

```
Triggers → Clustering → Classification → Verification → Scoring → Gates → Output
```

---

## Core Components

### Pipeline Architecture

- **[Scanner Pipeline](SCANNER_PIPELINE.md)** - Complete 7-stage pipeline documentation
  - Stage 1: Trigger Collection
  - Stage 2: Semantic Clustering
  - Stage 3: Source Classification
  - Stage 3.5: Event Verification (Gate 0)
  - Stage 4: Confidence Scoring
  - Stage 5: Content Gates
  - Stage 6-7: Final Filtering & Output

### Verification Systems

- **[Event Verification](EVENT_VERIFICATION.md)** - Gate 0: 3-stage hybrid verification
  - Stage 1: Rule-based patterns ($0)
  - Stage 2: Zero-shot classification (BART-MNLI, $0)
  - Stage 3: LLM verification (edge cases only)

- **[Claim Verification](CLAIM_VERIFICATION.md)** - v3.0 Claim-level verification
  - VeriScore-style claim extraction
  - QA-based LLM verification
  - AP Style article generation

### ML Components

- **[Zero-shot Classifier](ZERO_SHOT_CLASSIFIER.md)** - BART-MNLI classification
  - CAMEO/ACLED-based labels
  - International affairs detection
  - 70% LLM cost reduction

### Supporting Systems

- **Deduplication** - See [algorithms/DEDUPLICATION.md](../algorithms/DEDUPLICATION.md)
- **Bilingual Generation** - Korean/English article generation

---

## System Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬──────────────────┤
│    GDELT    │    USGS     │    NOAA     │   Reddit    │    Telegram      │
│  (Tier-1)   │  (Tier-1)   │  (Tier-1)   │  (Tier-3)   │    (Tier-3)      │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │             │               │
       └─────────────┴─────────────┴─────────────┴───────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      TRIGGER MANAGER        │
                    │   Parallel event collection │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     SEMANTIC CLUSTERING     │
                    │   BGE-M3 + HDBSCAN         │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     EVENT VERIFICATION      │
                    │   Rules → Zero-shot → LLM   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │    CONFIDENCE SCORING       │
                    │  Two-Source Rule + Tiers    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      CONTENT GATES          │
                    │ Checkworthiness + Specificity│
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   CLAIM VERIFICATION        │
                    │  Extract → Verify → Write   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       ARTICLE OUTPUT        │
                    │   Bilingual (KO/EN) + DB    │
                    └─────────────────────────────┘
```

---

## Key Design Decisions

For rationale behind architectural choices, see:

- [ADR-001: Two-Source Rule](../adr/ADR-001-two-source-rule.md)
- [ADR-002: Gate Ordering](../adr/ADR-002-gate-ordering.md)
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md)
- [ADR-004: Hybrid Verification](../adr/ADR-004-hybrid-verification.md)
- [ADR-005: Bilingual Generation](../adr/ADR-005-bilingual-generation.md)
- [ADR-006: Deduplication](../adr/ADR-006-deduplication.md)

---

## Performance Characteristics

| Component | Latency | Cost | Accuracy |
|-----------|---------|------|----------|
| Trigger scan | 8-10s | $0 | N/A |
| Clustering | 1-3s | $0 | ~95% |
| Event verification | 350ms | $1.44/day | ~90% |
| Claim verification | 60-120s | ~$50/month | ~90% |

---

## Related Documentation

- [Algorithms](../algorithms/README.md) - Detailed algorithm documentation
- [API Reference](../api/README.md) - REST endpoints
- [Configuration](../guides/CONFIGURATION.md) - All settings
