# Core Concepts

This section explains the fundamental concepts and principles that guide the LiveMap system.

---

## Overview

LiveMap is built on three foundational principles:

1. **Multi-source verification** - No single source of truth
2. **Transparency** - Open methodology and confidence scores
3. **Speed with accuracy** - Real-time but verified

---

## Key Concepts

### Verification & Trust

- **[Two-Source Rule](TWO_SOURCE_RULE.md)** - Why we require 2+ independent sources
- **[Source Tiers](SOURCE_TIERS.md)** - How sources are classified and weighted
- **[Confidence Scoring](CONFIDENCE_SCORING.md)** - How trust scores are calculated

### Focus & Strategy

- **[International Affairs Focus](INTERNATIONAL_AFFAIRS.md)** - Why we focus on 7 categories

---

## Quick Reference

### Source Tier Summary

| Tier | Credibility | Examples | Single-source publish? |
|------|-------------|----------|------------------------|
| Tier-1 Govt | 0.99 | USGS, NOAA | Yes |
| Tier-1 News | 0.90 | GDELT | Yes (≥0.70) |
| Tier-2 Data | 0.85 | ACLED | No |
| Tier-2 News | 0.75 | Currents, WorldNews | No |
| Tier-3 Social | 0.40 | Reddit, Bluesky | No |
| Tier-3 Msg | 0.35 | Telegram | No |

### Category Summary

| Category | Scope | Examples |
|----------|-------|----------|
| war | Armed conflict | Invasions, airstrikes |
| conflict | Regional disputes | Border clashes, civil wars |
| politics | International politics | Summits, sanctions |
| security | Security threats | Nuclear, cyber |
| military | Military activities | Operations, deployments |
| terrorism | Terror events | Attacks, organizations |
| diplomacy | Diplomatic activities | Treaties, negotiations |

---

## IFCN Principles

LiveMap follows the International Fact-Checking Network's 5 principles:

| Principle | Our Implementation |
|-----------|-------------------|
| Non-partisanship | Algorithm-based, no editorial bias |
| Source transparency | All sources cited in every article |
| Funding transparency | No advertising or sponsored content |
| Methodology transparency | Open documentation |
| Corrections policy | Immediate correction on errors |

---

## Related Documentation

- [Architecture](../architecture/README.md) - Technical implementation
- [Algorithms](../algorithms/README.md) - Detailed algorithms
