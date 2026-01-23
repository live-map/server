# Algorithm Documentation

Detailed documentation of the algorithms used in LiveMap.

---

## Overview

LiveMap uses several key algorithms for event processing:

1. **Cross-Source Matching** - Finding the same event across sources
2. **Confidence Scoring** - Calculating trust scores
3. **Deduplication** - Removing duplicate events

---

## Contents

| Algorithm | Purpose | Key Technology |
|-----------|---------|----------------|
| [**Cross-Source Matcher**](CROSS_SOURCE_MATCHER.md) | Match events across sources | BGE-M3 embeddings, cosine similarity |
| [**Confidence Scoring**](CONFIDENCE_SCORING.md) | Calculate trust scores | Tier weighting, diversity bonus |
| [**Deduplication**](DEDUPLICATION.md) | Remove duplicates | Two-layer (intra-scan, inter-scan) |

---

## Algorithm Summary

### Cross-Source Matching

```
Event A (GDELT) ──┐
                  ├── Similarity > 0.70 ──► Same Event
Event B (Reddit) ─┘
```

Uses BGE-M3 embeddings to compute semantic similarity between events from different sources.

### Confidence Scoring

```
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus

Where:
- base_score: 0.50 (1 source), 0.70 (2 sources), 0.85 (3+)
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

---

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cross_source_similarity_threshold` | 0.70 | Min similarity for match |
| `min_confidence_score` | 0.70 | Publication threshold |
| `dedup_similarity_threshold` | 0.85 | Duplicate threshold |
| `clustering_min_cluster_size` | 2 | HDBSCAN parameter |

---

## Performance Characteristics

| Algorithm | Time Complexity | Space | Typical Latency |
|-----------|-----------------|-------|-----------------|
| Cross-Source | O(n²) | O(n) | ~100ms for 100 events |
| Confidence | O(n) | O(1) | ~1ms per event |
| Deduplication | O(n log n) | O(n) | ~500ms for 100 events |

---

## Related Documentation

- [Scanner Pipeline](../architecture/SCANNER_PIPELINE.md) - How algorithms fit in pipeline
- [Configuration](../guides/CONFIGURATION.md) - Algorithm parameters
