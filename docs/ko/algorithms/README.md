# 알고리즘 문서

LiveMap에서 사용하는 알고리즘에 대한 상세 문서입니다.

---

## 개요

LiveMap은 이벤트 처리를 위해 여러 핵심 알고리즘을 사용합니다:

1. **Cross-Source Matching** - 여러 소스에서 동일한 이벤트 찾기
2. **Confidence Scoring** - 도메인 티어 통합 신뢰도 점수 계산
3. **Deduplication** - 중복 이벤트 제거
4. **Importance Scoring** - 다차원 이벤트 중요도 평가
5. **Source Tiers** - 도메인 기반 신뢰도 분류

---

## 목차

| 알고리즘 | 목적 | 핵심 기술 |
|----------|------|-----------|
| [**Cross-Source Matcher**](CROSS_SOURCE_MATCHER.md) | 여러 소스 간 이벤트 매칭 | BGE-M3 embeddings, cosine similarity |
| [**Confidence Scoring**](CONFIDENCE_SCORING.md) | 신뢰도 점수 계산 | 티어 가중치, 도메인 통합 |
| [**Deduplication**](DEDUPLICATION.md) | 중복 제거 | Two-layer (intra-scan, inter-scan) |
| [**Importance Scoring**](IMPORTANCE_SCORING.md) | 이벤트 중요도 평가 | Goldstein Scale, 6차원 점수 |
| [**Source Tiers**](SOURCE_TIERS.md) | 도메인 신뢰도 분류 | 4티어 시스템, 게시 규칙 |

---

## 알고리즘 요약

### Cross-Source Matching

```
Event A (GDELT) ──┐
                  ├── Similarity > 0.75 ──► 동일 이벤트
Event B (Reddit) ─┘
```

BGE-M3 임베딩을 사용하여 서로 다른 소스의 이벤트 간 의미적 유사도를 계산합니다.

### Confidence Scoring

```
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus

Where:
- base_score: 0.50-0.75 (1 소스, 티어에 따라), 0.70 (2 소스), 0.85 (3+)
- tier_average: 모든 소스의 평균 신뢰도
- diversity_bonus: 다른 티어의 소스가 있으면 +0.03
```

### Importance Scoring

```
중요도 = (이벤트_유형 × 0.20) +        # Goldstein Scale
        (행위자_중요도 × 0.20) +        # P5, G7, 지역 강대국
        (지리적_범위 × 0.15) +          # 지역 → 국제
        (사상자_규모 × 0.15) +          # 로그 스케일
        (소스_커버리지 × 0.15) +        # Tier-1/2 존재
        (확대_가능성 × 0.15)            # 위험 평가

수준:
- CRITICAL (0.70-1.00): 즉시 처리
- HIGH (0.50-0.69): 표준 처리
- MEDIUM (0.30-0.49): 검토 필요
- LOW (0.00-0.29): 필터링
```

### Source Tiers

```
Tier-1 (0.95): 통신사 (Reuters, AP, AFP, 정부)
  └── 단일 소스 OK, 지연 없음, 패스트패스 자격

Tier-2 (0.85): 주요 매체 (BBC, NYT, CNN, Guardian)
  └── 단일 소스 OK, 60분 검증, 패스트패스 자격

Tier-3 (0.70): 지역/전문 (LA Times, Nature)
  └── Two-Source Rule 필요

Tier-4 (0.50): 기타 (블로그, 알 수 없음)
  └── 3개 이상 소스 필요
```

---

## 주요 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `cross_source_similarity_threshold` | 0.75 | 매칭을 위한 최소 유사도 |
| `min_confidence_score` | 0.70 | 게시 임계값 |
| `dedup_similarity_threshold` | 0.85 | 중복 판정 임계값 |
| `clustering_min_cluster_size` | 2 | HDBSCAN 파라미터 |
| `min_importance_threshold` | 0.25 | 중요도 필터 임계값 |

---

## 성능 특성

| 알고리즘 | 시간 복잡도 | 공간 | 일반적 지연 |
|----------|------------|------|------------|
| Cross-Source | O(n²) | O(n) | 100개 이벤트 기준 ~100ms |
| Confidence | O(n) | O(1) | 이벤트당 ~1ms |
| Deduplication | O(n log n) | O(n) | 100개 이벤트 기준 ~500ms |
| Importance | O(n) | O(1) | 이벤트당 ~5ms |
| Source Tier | O(1) | O(1) | 조회당 <1ms |

---

## 관련 문서

- [Scanner Pipeline](../architecture/SCANNER_PIPELINE.md) - 알고리즘이 파이프라인에 어떻게 적용되는지
- [Configuration](../guides/CONFIGURATION.md) - 알고리즘 파라미터
- [ADR-003: 티어 시스템](../adr/ADR-003-tier-system.md) - 트리거 티어 결정
- [ADR-008: 중요도 점수](../adr/ADR-008-importance-scoring.md) - Goldstein Scale 채택
- [ADR-011: 도메인 티어](../adr/ADR-011-domain-tiers.md) - 도메인 티어 결정
