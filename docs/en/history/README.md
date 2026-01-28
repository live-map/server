# Project History

This section documents the evolution of the LiveMap system from initial concept to current implementation.

---

## Timeline Overview

```
Jan 10, 2026 ──────────────────────────────────────────────────────► Jan 27
    │
    ├── Phase 0: Foundation (Jan 10)
    │   └── Telegram MCP, GDELT trigger, basic infrastructure
    │
    ├── Phase 1: Verification Evolution (Jan 10-14)
    │   └── 3-stage → RAG → GDELT → Claim-level SOTA
    │
    ├── Phase 2: Security and Quality (Jan 15-19)
    │   └── JWT → JWE migration, significance scoring
    │
    ├── Phase 3: Intelligence Layer (Jan 19-23)
    │   └── Zero-shot ML, 91% cost reduction, gate system
    │
    ├── Phase 4: Source Management (Jan 23-24)
    │   └── Recency filters, category classification
    │
    ├── Phase 5: Optimization (Jan 24)
    │   └── Breaking news fast-path, P0/P1/P2 optimizations
    │
    └── Phase 6: LLM Classifier (Jan 25-27)
        └── Patterns → LLM, Recency removal, Pre-LLM Dedup
```

---

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| v0.1 | Jan 10 | Basic trigger system |
| v1.0 | Jan 11 | 3-stage verification |
| v2.0 | Jan 13 | Deep verification agent |
| v3.0 | Jan 14 | Claim-level verification (SOTA) |
| v3.1 | Jan 14 | Production-ready quality |
| v3.2 | Jan 21 | Gate system integration |
| v3.3 | Jan 23 | Zero-shot ML classifier |
| v3.4 | Jan 24 | Breaking news fast-path |
| v3.5 | Jan 24 | P0/P1/P2 optimizations |
| v3.6 | Jan 27 | **LLM Classifier + Pipeline optimization** |

---

## Phase Documentation

### Current Architecture (Phase 6)

The system now uses LLM-based classification with optimized deduplication:

| Phase | Document | Summary |
|-------|----------|---------|
| 0 | [Foundation](PHASE_0_FOUNDATION.md) | Telegram MCP, GDELT, basic setup |
| 1 | [Verification Evolution](PHASE_1_VERIFICATION_EVOLUTION.md) | 3-stage → Claim-level SOTA |
| 2 | [Security and Quality](PHASE_2_SECURITY_AND_QUALITY.md) | JWE auth, significance scoring |
| 3 | [Intelligence Layer](PHASE_3_INTELLIGENCE_LAYER.md) | Zero-shot ML, 91% cost reduction |
| 4 | [Source Management](PHASE_4_SOURCE_MANAGEMENT.md) | Recency filters, categories |
| 5 | [Optimization](PHASE_5_OPTIMIZATION.md) | Breaking news, P0/P1/P2 |
| **6** | [**LLM Classifier**](PHASE_6_LLM_CLASSIFIER.md) | **Patterns→LLM, Recency removal, Pre-LLM Dedup** |

---

## Key Metrics

| Metric | Initial | Phase 5 | Phase 6 (Current) | Improvement |
|--------|---------|---------|-------------------|-------------|
| LLM cost/day | $16.13 | $1.44 | **$0.10-0.17** | -99% |
| Verification time | 45s | 8s avg | 5s avg | -89% |
| Breaking news latency | N/A | 5s | 5s | - |
| Pattern rules | 600+ | 600+ | **1 prompt** | -99% |
| Data sources | 1 | 12+ | **59 domains** (whitelist) | Quality↑ |
| False positive rate | ~20% | ~5% | ~5% (expected) | - |

---

## Archived Documents

Documents for deprecated approaches:

- [Phase 7 Zero-Shot (Original)](archive/PHASE_7_ZERO_SHOT.md) - Merged into Phase 3
- [Deep Verification v2.0](archive/DEEP_VERIFICATION_V2.md) - Replaced by v3.0 claim-level
- [Claim Verification Plan](archive/CLAIM_VERIFICATION_PLAN.md) - Completed planning doc
- [Methodology](archive/METHODOLOGY.md) - Original methodology

---

## Key Decisions Timeline

| Date | Decision | Rationale | ADR |
|------|----------|-----------|-----|
| Jan 10 | Two-Source Rule | IFCN compliance | [ADR-001](../adr/ADR-001-two-source-rule.md) |
| Jan 11 | Tier system (Triggers) | Differentiate source credibility | [ADR-003](../adr/ADR-003-tier-system.md) |
| Jan 13 | VeriScore claims | 2026 SOTA implementation | - |
| Jan 15 | Gate ordering | Most → least expensive | [ADR-002](../adr/ADR-002-gate-ordering.md) |
| Jan 21 | Hybrid verification | 70% LLM cost reduction | [ADR-004](../adr/ADR-004-hybrid-verification.md) |
| Jan 23 | Zero-shot classifier | Additional 70% reduction | [ADR-004](../adr/ADR-004-hybrid-verification.md) |
| Jan 23 | International focus | Quality over quantity | - |
| Jan 24 | Breaking news fast-path | Speed for Tier-1 sources | [ADR-007](../adr/ADR-007-breaking-news.md) |
| Jan 24 | Domain tier system | Per-domain credibility | [ADR-011](../adr/ADR-011-domain-tiers.md) |
| Jan 24 | Goldstein Scale importance | Multi-dimension scoring | [ADR-008](../adr/ADR-008-importance-scoring.md) |
| Jan 27 | **LLM Classifier** | 600 patterns → 1 prompt | [ADR-012](../adr/ADR-012-llm-classifier.md) |
| Jan 27 | **Recency Filter Removal** | Triggers already handle it | - |
| Jan 27 | **Pre-LLM Dedup** | 25% LLM cost savings | - |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## Related Documentation

- [Architecture Decisions](../adr/README.md) - ADRs
- [Architecture](../architecture/README.md) - Current design
- [Algorithms](../algorithms/README.md) - Core algorithms
