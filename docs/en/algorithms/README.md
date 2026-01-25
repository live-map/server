# Algorithm Documentation

Detailed documentation of the algorithms used in LiveMap.

---

## Overview

LiveMap uses several key algorithms for event processing:

1. **Cross-Source Matching** - Finding the same event across sources
2. **Confidence Scoring** - Calculating trust scores with domain tier integration
3. **Deduplication** - Removing duplicate events
4. **Importance Scoring** - Multi-dimension event importance evaluation
5. **Source Tiers** - Domain-based credibility classification

---

## Contents

| Algorithm | Purpose | Key Technology |
|-----------|---------|----------------|
| [**Cross-Source Matcher**](CROSS_SOURCE_MATCHER.md) | Match events across sources | BGE-M3 embeddings, cosine similarity |
| [**Confidence Scoring**](CONFIDENCE_SCORING.md) | Calculate trust scores | Tier weighting, domain integration |
| [**Deduplication**](DEDUPLICATION.md) | Remove duplicates | Two-layer (intra-scan, inter-scan) |
| [**Importance Scoring**](IMPORTANCE_SCORING.md) | Evaluate event significance | Goldstein Scale, 6-dimension scoring |
| [**Source Tiers**](SOURCE_TIERS.md) | Classify domain credibility | 4-tier system, publication rules |

---

## Algorithm Summary

### Cross-Source Matching

```
Event A (GDELT) ──┐
                  ├── Similarity > 0.75 ──► Same Event
Event B (Reddit) ─┘
```

Uses BGE-M3 embeddings to compute semantic similarity between events from different sources.

### Confidence Scoring

```
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus

Where:
- base_score: 0.50-0.75 (1 source, depends on tier), 0.70 (2 sources), 0.85 (3+)
- tier_average: Mean credibility of all sources
- diversity_bonus: +0.03 if sources from different tiers
```

### Deduplication

```
Layer 1: Intra-scan (within same scan)
  └── HDBSCAN clustering on embeddings

Layer 2: Inter-scan (against database)
  └── pgvector cosine similarity < 0.15 (= similarity > 0.85)
```

### Importance Scoring

```
importance = (event_type × 0.20) +        # Goldstein Scale
             (actor_significance × 0.20) +  # P5, G7, regional powers
             (geographic_scope × 0.15) +    # Local → International
             (casualty_scale × 0.15) +      # Log scale
             (source_coverage × 0.15) +     # Tier-1/2 presence
             (escalation_potential × 0.15)  # Risk assessment

Levels:
- CRITICAL (0.70-1.00): Immediate processing
- HIGH (0.50-0.69): Standard processing
- MEDIUM (0.30-0.49): Review required
- LOW (0.00-0.29): Filtered out
```

### Source Tiers

```
Tier-1 (0.95): Wire services (Reuters, AP, AFP, government)
  └── Single source OK, no delay, fast-path eligible

Tier-2 (0.85): Major outlets (BBC, NYT, CNN, Guardian)
  └── Single source OK, 60-min verify, fast-path eligible

Tier-3 (0.70): Regional/specialty (LA Times, Nature)
  └── Two-Source Rule required

Tier-4 (0.50): Other (blogs, unknown)
  └── 3+ sources required
```

---

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cross_source_similarity_threshold` | 0.75 | Min similarity for match |
| `min_confidence_score` | 0.70 | Publication threshold |
| `dedup_similarity_threshold` | 0.85 | Duplicate threshold |
| `clustering_min_cluster_size` | 2 | HDBSCAN parameter |
| `min_importance_threshold` | 0.25 | Importance filter threshold |

---

## Performance Characteristics

| Algorithm | Time Complexity | Space | Typical Latency |
|-----------|-----------------|-------|-----------------|
| Cross-Source | O(n²) | O(n) | ~100ms for 100 events |
| Confidence | O(n) | O(1) | ~1ms per event |
| Deduplication | O(n log n) | O(n) | ~500ms for 100 events |
| Importance | O(n) | O(1) | ~5ms per event |
| Source Tier | O(1) | O(1) | <1ms per lookup |

---

## Related Documentation

- [Scanner Pipeline](../architecture/SCANNER_PIPELINE.md) - How algorithms fit in pipeline
- [Configuration](../guides/CONFIGURATION.md) - Algorithm parameters
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md) - Trigger tier decisions
- [ADR-008: Importance Scoring](../adr/ADR-008-importance-scoring.md) - Goldstein Scale adoption
- [ADR-011: Domain Tiers](../adr/ADR-011-domain-tiers.md) - Domain tier decisions
