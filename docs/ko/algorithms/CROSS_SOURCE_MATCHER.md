# Cross-Source Matcher Algorithm

## Overview

Cross-Source Matcher는 서로 다른 소스에서 보도된 동일한 뉴스 이벤트를 식별합니다. 이를 통해 다음이 가능합니다:
- 다중 소스 검증 (Two-Source Rule)
- 신뢰도 점수 향상
- 이벤트 클러스터링 및 중복 제거

## Algorithm Flow

```
Input: List of TriggerEvents from various sources
  ↓
1. Time Window Filter (6 hours default)
  ↓
2. Generate Embeddings (BGE-M3, 1024 dims)
  ↓
3. Compute Similarity Matrix (Cosine)
  ↓
4. Find Cross-Source Matches (threshold >= 0.70)
  ↓
5. Create MatchedEvent Groups
  ↓
Output: List of MatchedEvents (clustered by similarity)
```

## Step 1: Time Window Filtering

이벤트는 설정 가능한 시간 창(기본값: 6시간)으로 필터링됩니다.

```python
cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)
recent_events = [e for e in events if e.detected_at >= cutoff]
```

**근거:** 동일한 이벤트에 대한 뉴스는 일반적으로 몇 시간 내에 나타납니다. 오래된 이벤트는 새로운 보도와 관련이 있을 가능성이 낮습니다.

## Step 2: Embedding Generation

각 이벤트는 BGE-M3를 사용하여 1024차원 벡터로 변환됩니다.

### Text Preparation
```python
def _get_event_text(event: TriggerEvent) -> str:
    parts = [event.title]
    if event.content:
        parts.append(event.content[:500])  # Truncate long content
    return " ".join(parts)
```

### Embedding Model
- **Model:** BAAI/bge-m3
- **Dimensions:** 1024
- **Normalization:** cosine similarity를 위한 L2 정규화

```python
embeddings = encoder.encode(
    texts,
    normalize_embeddings=True,
    show_progress_bar=False,
)
```

### Fallback
임베딩 모델을 사용할 수 없는 경우 Jaccard 유사도로 대체합니다:

```python
def _text_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0
```

## Step 3: Similarity Matrix

모든 이벤트 간의 쌍별 cosine similarity를 계산합니다.

```python
# With normalized embeddings, dot product = cosine similarity
similarity_matrix = np.dot(embeddings, embeddings.T)
```

**결과:** `matrix[i][j]`가 이벤트 i와 j 사이의 유사도인 N×N 행렬.

## Step 4: Cross-Source Matching

소스 제약 조건과 함께 유사도 임계값을 기반으로 매칭을 찾습니다.

```python
for i in range(n):
    for j in range(n):
        if i == j or j in matched_indices:
            continue

        sim = similarity_matrix[i, j]
        if sim >= similarity_threshold:
            # CRITICAL: Only match if from DIFFERENT sources
            if events[i].source != events[j].source:
                similar_indices.append(j)
                similar_scores.append(sim)
```

**핵심 규칙:** 동일한 소스의 이벤트는 절대 함께 매칭되지 않습니다. 이를 통해 다음을 방지합니다:
- 동일 매체의 중복 기사 카운팅
- 자기 검증 (소스가 스스로를 검증할 수 없음)

## Step 5: MatchedEvent Creation

매칭된 이벤트를 MatchedEvent 객체로 그룹화합니다.

```python
@dataclass
class MatchedEvent:
    primary_event: TriggerEvent
    matching_events: list[TriggerEvent]
    similarity_scores: list[float]

    @property
    def source_count(self) -> int:
        sources = set(e.source for e in self.all_events)
        return len(sources)

    @property
    def sources(self) -> list[dict]:
        # Returns source names with tier info
```

## Configuration

```python
CrossSourceMatcher(
    similarity_threshold=0.70,  # 매칭을 위한 최소 유사도
    time_window_hours=6,        # 이 시간 창 내의 이벤트
    embedding_model="BAAI/bge-m3"  # 임베딩 모델
)
```

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Embedding latency | ~100ms per event |
| Similarity computation | O(n²) |
| Memory (1000 events) | ~4MB embeddings |
| Recommended batch size | 100-500 events |

## Example

**입력 이벤트:**
1. GDELT: "Iran launches drone attack on US base in Iraq"
2. Reddit: "Breaking: US base in Iraq under attack from Iran"
3. GDELT: "Earthquake strikes Turkey, 10 dead"

**Similarity Matrix:**
```
       Event1  Event2  Event3
Event1  1.00    0.85    0.15
Event2  0.85    1.00    0.12
Event3  0.15    0.12    1.00
```

**출력:**
```python
MatchedEvent(
    primary_event=Event1,  # GDELT Iran story
    matching_events=[Event2],  # Reddit Iran story (different source!)
    similarity_scores=[0.85]
)
MatchedEvent(
    primary_event=Event3,  # Earthquake (no matches)
    matching_events=[],
    similarity_scores=[]
)
```

## Implementation

```
app/agent/cross_source_matcher.py
```

## Related Documentation
- [Confidence Scoring](CONFIDENCE_SCORING.md)
- [Deduplication](DEDUPLICATION.md)
- [ADR-001: Two-Source Rule](../adr/ADR-001-two-source-rule.md)
