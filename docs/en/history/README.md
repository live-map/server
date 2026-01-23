# Project History

This section documents the evolution of the LiveMap system from initial concept to current implementation.

---

## Timeline Overview

```
Jan 10, 2026 ──────────────────────────────────────────────────────────────────►
    │
    ├── Phase 0: Foundation (Jan 10)
    │   └── Telegram MCP, basic trigger system
    │
    ├── Phase 1: Verification (Jan 10-11)
    │   └── 3-stage verification pipeline
    │
    ├── Phase 2: Autonomous Agent (Jan 11-13)
    │   └── Multi-source investigation, claim verification
    │
    ├── Phase 3: Parallel Processing (Jan 13)
    │   └── LangGraph agents, parallel evidence gathering
    │
    ├── Phase 4: Content Filtering (Jan 15-21)
    │   └── Gate 0-2, event verification, checkworthiness
    │
    ├── Phase 5: Integration (Jan 21-22)
    │   └── Scanner-Agent integration, DB persistence
    │
    ├── Phase 6: International Focus (Jan 23)
    │   └── 7 category focus, resource optimization
    │
    └── Phase 7: Zero-shot ML (Jan 23)
        └── BART-MNLI classifier, 91% cost reduction
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

---

## Phase Documentation

### Current Architecture (Phase 7)

The system now uses a 7-stage pipeline with 3-stage hybrid verification:

1. [Phase 0: Foundation](PHASE_0_FOUNDATION.md) - Initial Telegram MCP
2. [Phase 1: Verification](PHASE_1_VERIFICATION.md) - 3-stage pipeline
3. [Phase 2: Autonomous Agent](PHASE_2_AUTONOMOUS.md) - Multi-source investigation
4. [Phase 3: Parallel Processing](PHASE_3_PARALLEL.md) - LangGraph agents
5. [Phase 4: Content Filtering](PHASE_4_FILTERING.md) - Gate system
6. [Phase 5: Integration](PHASE_5_INTEGRATION.md) - Full pipeline
7. [Phase 6: International Focus](PHASE_6_INTERNATIONAL.md) - Category focus
8. [Phase 7: Zero-shot ML](PHASE_7_ZERO_SHOT.md) - ML classifier

---

## Archived Documents

Documents for deprecated approaches:

- [Deep Verification v2.0](archive/DEEP_VERIFICATION_V2.md) - Replaced by v3.0 claim-level
- [Claim Verification Plan](archive/CLAIM_VERIFICATION_PLAN.md) - Completed planning doc

---

## Key Decisions Timeline

| Date | Decision | Rationale |
|------|----------|-----------|
| Jan 10 | Two-Source Rule | IFCN compliance |
| Jan 11 | Tier system | Differentiate source credibility |
| Jan 13 | VeriScore claims | 2026 SOTA implementation |
| Jan 15 | Gate ordering | Most → least expensive |
| Jan 21 | Hybrid verification | 70% LLM cost reduction |
| Jan 23 | Zero-shot classifier | Additional 70% reduction |
| Jan 23 | International focus | Quality over quantity |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## Related Documentation

- [Architecture Decisions](../adr/README.md) - ADRs
- [Architecture](../architecture/README.md) - Current design
