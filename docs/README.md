# LiveMap Backend Documentation

Welcome to the LiveMap backend documentation. This directory contains comprehensive documentation for the news intelligence system.

## Quick Start

- **[Getting Started](GETTING_STARTED.md)** - Setup guide for new developers (5 minutes)
- **[Configuration Reference](CONFIG_REFERENCE.md)** - All environment variables and settings

## Core Documentation

### System Design
- **[Methodology](METHODOLOGY.md)** - Core methodology and principles
- **[Scanner Pipeline](SCANNER_PIPELINE.md)** - 7-stage pipeline architecture
- **[Event Verification](EVENT_VERIFICATION.md)** - Gate 0 3-stage hybrid verification
- **[Zero-shot Classification](ZERO_SHOT_CLASSIFICATION.md)** - Stage 2 ML-based event classification
- **[International Affairs Focus](INTERNATIONAL_AFFAIRS_FOCUS.md)** - Category definitions

### Architecture Decisions (ADRs)
- **[ADR Index](adr/README.md)** - All architecture decision records
- [ADR-001: Two-Source Rule](adr/ADR-001-two-source-rule.md)
- [ADR-002: Gate Ordering](adr/ADR-002-gate-ordering.md)
- [ADR-003: Tier System](adr/ADR-003-tier-system.md)
- [ADR-004: Hybrid Verification](adr/ADR-004-hybrid-verification.md)
- [ADR-005: Bilingual Generation](adr/ADR-005-bilingual-generation.md)
- [ADR-006: Deduplication](adr/ADR-006-deduplication.md)

### API Reference
- **[API Reference](api/README.md)** - REST API endpoints with examples

### Algorithms
- **[Cross-Source Matcher](algorithms/CROSS_SOURCE_MATCHER.md)** - Semantic event matching
- **[Confidence Scoring](algorithms/CONFIDENCE_SCORING.md)** - Multi-source confidence calculation
- **[Deduplication](algorithms/DEDUPLICATION.md)** - Two-layer event deduplication

### Guides
- **[Trigger Guide](guides/TRIGGER_GUIDE.md)** - Adding new data sources
- **[Testing Guide](guides/TESTING_GUIDE.md)** - Running and writing tests

## Document Index

```
docs/
├── README.md                    # This file
├── GETTING_STARTED.md          # Quick setup guide
├── CONFIG_REFERENCE.md         # Configuration options
├── METHODOLOGY.md              # Core methodology
├── SCANNER_PIPELINE.md         # Pipeline architecture
├── EVENT_VERIFICATION.md       # Gate 0 3-stage verification
├── ZERO_SHOT_CLASSIFICATION.md # Stage 2 ML classification
├── INTERNATIONAL_AFFAIRS_FOCUS.md  # Category focus
├── CODE.md                     # Code organization
├── adr/                        # Architecture Decision Records
│   ├── README.md
│   ├── ADR-001-two-source-rule.md
│   ├── ADR-002-gate-ordering.md
│   ├── ADR-003-tier-system.md
│   ├── ADR-004-hybrid-verification.md
│   ├── ADR-005-bilingual-generation.md
│   └── ADR-006-deduplication.md
├── api/                        # API documentation
│   └── README.md
├── algorithms/                 # Algorithm documentation
│   ├── CROSS_SOURCE_MATCHER.md
│   ├── CONFIDENCE_SCORING.md
│   └── DEDUPLICATION.md
└── guides/                     # How-to guides
    ├── TRIGGER_GUIDE.md
    └── TESTING_GUIDE.md
```

## Key Concepts

### Source Tiers

| Tier | Sources | Credibility |
|------|---------|-------------|
| Tier-1 Govt | USGS, NOAA | 0.99 |
| Tier-1 News | GDELT | 0.90 |
| Tier-2 Data | ACLED | 0.85 |
| Tier-2 News | Currents, WorldNews | 0.75 |
| Tier-3 Social | Reddit, Twitter | 0.40 |
| Tier-3 Msg | Telegram | 0.35 |
| Tier-3 Trend | Google Trends | 0.30 |

### Pipeline Stages

1. **Trigger Collection** - Multi-source event gathering
2. **Clustering** - Semantic grouping
3. **Classification** - Tier-based source categorization
4. **Event Verification** - Gate 0 filtering
5. **Confidence Scoring** - Two-Source Rule
6. **Content Gates** - Quality filtering
7. **Final Output** - Category limiting

### Filtering Gates

| Gate | Purpose | Method |
|------|---------|--------|
| Gate 0 | Real event? | 3-stage hybrid (Rules → Zero-shot → LLM) |
| Gate 1 | Newsworthy? | Pattern matching |
| Gate 2 | Specific? | Pattern matching |
| Gate 3 | Evidence? | Claim verification |

#### Gate 0: 3-Stage Pipeline

| Stage | Method | Cost | Filter Rate |
|-------|--------|------|-------------|
| Stage 1 | Rule-based patterns | $0 | ~70% |
| Stage 2 | Zero-shot (BART-MNLI) | $0 | ~70% of remaining |
| Stage 3 | LLM verification | $0.001/event | Edge cases only |

## Contributing to Documentation

When adding new documentation:

1. Place in appropriate directory
2. Update this README index
3. Link from related documents
4. Follow markdown conventions
5. Include code examples where relevant
