# PM Reading Guide

> A structured reading path for Project Managers to understand the LiveMap system

---

## Target Audience & Reading Paths

| Role | Time Required | Essential Documents |
|------|---------------|---------------------|
| **Investor** | 20 min | OVERVIEW → INVESTOR_SUMMARY → COMPETITIVE_ANALYSIS |
| **Project Manager** | 90 min | Full path (below) |
| **Developer** | 60 min | getting-started → architecture → guides |
| **General User** | 10 min | OVERVIEW → getting-started/README |

---

## PM Reading Path (90 minutes)

### 1. Getting Started (5 min)

📖 **[OVERVIEW.md](./OVERVIEW.md)**: System at a glance
- What is LiveMap?
- Key differentiators
- High-level architecture

---

### 2. Business Understanding (15 min)

📖 **[business/INVESTOR_SUMMARY.md](./business/INVESTOR_SUMMARY.md)**: Why this project exists
- Problem statement
- Market opportunity
- Revenue model

📖 **[business/VALUE_PROPOSITION.md](./business/VALUE_PROPOSITION.md)**: Competitive advantages
- Cost comparison with alternatives
- Unique capabilities
- Target customers

📖 **[business/COMPETITIVE_ANALYSIS.md](./business/COMPETITIVE_ANALYSIS.md)**: Market positioning
- Competitor landscape
- Differentiation strategy
- Market gaps addressed

---

### 3. Core Concepts (20 min)

📖 **[concepts/TWO_SOURCE_RULE.md](./concepts/TWO_SOURCE_RULE.md)**: The foundation of our verification
- Why two sources matter
- Exception cases
- Implementation details

📖 **[concepts/SOURCE_TIERS.md](./concepts/SOURCE_TIERS.md)**: Source reliability framework
- Tier-1 Government sources
- Tier-1/2 News sources
- Tier-3 Social signals

📖 **[concepts/CONFIDENCE_SCORING.md](./concepts/CONFIDENCE_SCORING.md)**: How we calculate reliability
- Scoring formula
- Source weighting
- Publication thresholds

---

### 4. System Architecture (30 min)

📖 **[architecture/SCANNER_PIPELINE.md](./architecture/SCANNER_PIPELINE.md)**: 7-stage event processing
- Trigger collection
- Clustering & deduplication
- Event verification (Gate 0)
- Confidence scoring
- Content gates

📖 **[architecture/EVENT_VERIFICATION.md](./architecture/EVENT_VERIFICATION.md)**: Gate 0 verification
- 3-stage hybrid approach
- Rule-based filtering
- Zero-shot classification
- LLM verification

📖 **[architecture/ZERO_SHOT_CLASSIFIER.md](./architecture/ZERO_SHOT_CLASSIFIER.md)**: ML-based classification
- BART-large-MNLI model
- CAMEO/ACLED labels
- Confidence thresholds

📖 **[architecture/CLAIM_VERIFICATION.md](./architecture/CLAIM_VERIFICATION.md)**: Claim-level verification v3
- 5-stage pipeline
- VeriScore claim extraction
- QA-based verification
- AP Style article generation

---

### 5. Decision Records (15 min)

📖 **[adr/README.md](./adr/README.md)**: Architecture Decision Records overview
- What are ADRs?
- How to read them

📖 **Key ADRs to review:**
- [ADR-001: Two-Source Rule](./adr/ADR-001-two-source-rule.md) - Core verification principle
- [ADR-002: Gate Ordering](./adr/ADR-002-gate-ordering.md) - Pipeline design rationale
- [ADR-003: Tier System](./adr/ADR-003-tier-system.md) - Source classification
- [ADR-004: Hybrid Verification](./adr/ADR-004-hybrid-verification.md) - Event verification approach
- [ADR-005: Bilingual Generation](./adr/ADR-005-bilingual-generation.md) - Korean/English output
- [ADR-006: Deduplication](./adr/ADR-006-deduplication.md) - Duplicate event handling

---

### 6. [Optional] Developer Guides

If you need technical depth:

📖 **[getting-started/README.md](./getting-started/README.md)**: Quick start guide
- Installation steps
- Running the server
- First scan

📖 **[guides/CONFIGURATION.md](./guides/CONFIGURATION.md)**: System configuration
- Environment variables
- Feature flags
- Tuning parameters

---

### 7. [Optional] Project History

To understand how we got here:

📖 **[history/CHANGELOG.md](./history/CHANGELOG.md)**: Version history
- Major milestones
- Feature additions
- Breaking changes

📖 **[history/PHASE_7_ZERO_SHOT.md](./history/PHASE_7_ZERO_SHOT.md)**: Zero-shot classifier implementation
- Design decisions
- Performance benchmarks

---

## Quick Reference

### System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TRIGGER LAYER                                   │
│   GDELT (100K+ sources) + Telegram (OSINT) + X/Twitter               │
├─────────────────────────────────────────────────────────────────────┤
│                    DETECTION LAYER                                   │
│   Keyword Matching → Anomaly Detection → Semantic Clustering         │
├─────────────────────────────────────────────────────────────────────┤
│                   VERIFICATION LAYER                                 │
│   Gate 0 (Event) → Gate 1 (Check-worthy) → Gate 2 (Specificity)     │
├─────────────────────────────────────────────────────────────────────┤
│                   INVESTIGATION LAYER                                │
│   Claim Extraction → Evidence Retrieval → QA Verification           │
├─────────────────────────────────────────────────────────────────────┤
│                      OUTPUT LAYER                                    │
│   AP Style Article (EN/KO) + Per-Claim Breakdown                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Metrics

| Metric | Value |
|--------|-------|
| Monthly operating cost | ~$20 (vs competitors $10K-$200K) |
| Event detection delay | <15 min (GDELT), Real-time (Telegram) |
| Investigation time | ~65 sec (Deep Verification) |
| Language support | 100+ (BGE-M3 multilingual embedding) |
| Data sources | 100,000+ news sources + social media |

### Cost Comparison

| Solution | Annual Cost | vs LiveMap |
|----------|-------------|------------|
| Palantir | $173K+ | 720x |
| Dataminr | $120K-$2.4M | 500-10,000x |
| Recorded Future | $200K+ | 833x |
| **LiveMap** | **$240** | 1x |

---

## Questions?

If you have questions after reading:
1. Check [guides/TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md) for common issues
2. Review the [ADR index](./adr/README.md) for design decisions
3. Contact the development team

---

*This guide is maintained as part of the documentation bilingual structure.*
