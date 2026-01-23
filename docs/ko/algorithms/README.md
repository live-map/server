# Algorithm Documentation

LiveMap에서 사용하는 알고리즘에 대한 상세 문서입니다.

---

## Overview

LiveMap은 이벤트 처리를 위해 여러 핵심 알고리즘을 사용합니다:

1. **Cross-Source Matching** - 여러 소스에서 동일한 이벤트 찾기
2. **Confidence Scoring** - 신뢰도 점수 계산
3. **Deduplication** - 중복 이벤트 제거

---

## Contents

| Algorithm | Purpose | Key Technology |
|-----------|---------|----------------|
| [**Cross-Source Matcher**](CROSS_SOURCE_MATCHER.md) | 여러 소스 간 이벤트 매칭 | BGE-M3 embeddings, cosine similarity |
| [**Confidence Scoring**](CONFIDENCE_SCORING.md) | 신뢰도 점수 계산 | Tier weighting, diversity bonus |
| [**Deduplication**](DEDUPLICATION.md) | 중복 제거 | Two-layer (intra-scan, inter-scan) |

---

## Algorithm Summary

### Cross-Source Matching

```
Event A (GDELT) ──┐
                  ├── Similarity > 0.70 ──► Same Event
Event B (Reddit) ─┘
```

BGE-M3 임베딩을 사용하여 서로 다른 소스의 이벤트 간 의미적 유사도를 계산합니다.

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
| `cross_source_similarity_threshold` | 0.70 | 매칭을 위한 최소 유사도 |
| `min_confidence_score` | 0.70 | 게시 임계값 |
| `dedup_similarity_threshold` | 0.85 | 중복 판정 임계값 |
| `clustering_min_cluster_size` | 2 | HDBSCAN 파라미터 |

---

## Performance Characteristics

| Algorithm | Time Complexity | Space | Typical Latency |
|-----------|-----------------|-------|-----------------|
| Cross-Source | O(n²) | O(n) | 100개 이벤트 기준 ~100ms |
| Confidence | O(n) | O(1) | 이벤트당 ~1ms |
| Deduplication | O(n log n) | O(n) | 100개 이벤트 기준 ~500ms |

---

## Related Documentation

- [Scanner Pipeline](../architecture/SCANNER_PIPELINE.md) - 알고리즘이 파이프라인에 어떻게 적용되는지
- [Configuration](../guides/CONFIGURATION.md) - 알고리즘 파라미터
