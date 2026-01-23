# ADR-006: Two-Layer Deduplication

## Status
Accepted

## Context

여러 소스에서 대량의 뉴스를 집계하면 상당한 중복이 발생합니다:
- 다른 매체에서 보도한 동일한 기사
- 동일한 이벤트의 사소한 재작성
- 기존 기사에 대한 업데이트
- 관련되지만 별개인 이벤트

중복 제거가 없으면:
- 데이터베이스 비대화
- 중복 처리
- 나쁜 사용자 경험
- 리소스 낭비

다음을 수행하는 시스템이 필요했습니다:
1. 정확한 중복을 빠르게 포착
2. 의미론적 중복 식별 (같은 의미, 다른 단어)
3. 업데이트와 중복 구분
4. 관련 이벤트 연결

## Decision

**2계층 중복 제거 시스템**을 구현합니다:

### Layer 1: Hash Matching (O(1), Exact)

정규화된 텍스트 해싱을 사용한 빠른 정확한 매칭:

```python
def _generate_hash(text: str) -> str:
    # Normalize: lowercase, remove punctuation, collapse whitespace
    normalized = text.lower().strip()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)

    # SHA-256 hash
    return hashlib.sha256(normalized.encode()).hexdigest()
```

**특성:**
- 데이터베이스 인덱스를 통한 O(1) 조회
- 거짓 양성 없음
- 정확한 재게시를 포착

### Layer 2: Semantic Search (pgvector, Similar)

의미론적 매칭을 위한 벡터 유사도:

```python
# Using BGE-M3 embeddings (1024 dimensions)
# Cosine similarity via pgvector

SELECT id, 1 - (embedding <=> query_embedding) as similarity
FROM events
WHERE (embedding <=> query_embedding) <= (1 - 0.70)
ORDER BY embedding <=> query_embedding
LIMIT 1
```

**유사도 임계값:**

| Similarity | Match Type | Action |
|------------|------------|--------|
| 1.00 | EXACT | 건너뛰기 (해시 매칭) |
| >= 0.95 | DUPLICATE | 건너뛰기 |
| 0.85 - 0.95 | POTENTIAL | LLM 검증 |
| 0.70 - 0.85 | RELATED | 스토리 체인으로 연결 |
| < 0.70 | NEW | 새 이벤트 생성 |

### Decision Flow

```
Input Event
    ↓
Layer 1: Hash Match?
    ├─ Yes → EXACT duplicate → Skip
    ↓ No
Layer 2: Semantic Search
    ├─ >= 0.95 → DUPLICATE → Skip
    ├─ 0.85-0.95 → POTENTIAL → LLM decides
    ├─ 0.70-0.85 → RELATED → Link events
    └─ < 0.70 → NEW → Create event
```

## Consequences

### Positive
- **빠른 정확한 매칭**: 해시 조회가 O(1)
- **의미론적 이해**: 패러프레이즈된 중복을 포착
- **단계적 응답**: 다른 유사도 수준에 다른 동작
- **스토리 연결**: 관련 이벤트가 연결됨
- **구성 가능한 임계값**: 사용 사례별로 조정 가능
- **업데이트 감지**: 잠재적 매칭이 업데이트일 수 있음

### Negative
- **임베딩 비용**: 각 이벤트에 임베딩 생성이 필요함
- **저장소 오버헤드**: 이벤트당 1024차원 벡터
- **임계값 조정**: 경험적 조정이 필요함
- **pgvector 의존성**: 특수 데이터베이스 확장
- **잠재적 거짓 음성**: 낮은 유사도 임계값이 중복을 놓칠 수 있음

## Alternatives Considered

### Alternative A: Hash-Only Deduplication
정확한 해시 매칭만 사용합니다.

**기각 사유:**
- 의미론적으로 동일한 콘텐츠를 놓침
- 패러프레이즈된 중복이 통과함
- 높은 거짓 음성률

### Alternative B: LLM-Only Comparison
LLM을 사용하여 모든 이벤트 쌍을 비교합니다.

**기각 사유:**
- O(n^2) 비교
- 대규모로 매우 비쌈
- 느림 (비교당 수백 ms)
- 대부분의 경우에 과잉

### Alternative C: TF-IDF Similarity
전통적인 텍스트 유사도(TF-IDF, BM25)를 사용합니다.

**기각 사유:**
- 의미론적 이해가 없음
- 키워드 기반만
- 패러프레이즈된 콘텐츠에 취약함
- 임베딩보다 정확도가 낮음

### Alternative D: Bloom Filter Pre-Check
해시 검사 전에 블룸 필터를 추가합니다.

**향후 고려됨:**
- 해시 조회를 줄일 수 있음
- 확률적이며 복잡성 추가
- 현재 볼륨에는 필요하지 않음

## Implementation Details

### Embedding Model
- Model: BGE-M3 (BAAI/bge-m3)
- Dimensions: 1024
- 이유: 다국어, 품질/크기의 좋은 균형

### Database Schema
```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_hash VARCHAR(64) NOT NULL,
    embedding vector(1024),
    -- ... other fields
);

CREATE INDEX idx_event_hash ON events(event_hash);
CREATE INDEX idx_embedding ON events USING ivfflat (embedding vector_cosine_ops);
```

### Threshold Configuration
```python
# In agent_settings
dedup_duplicate_threshold: float = 0.95
dedup_potential_threshold: float = 0.85
dedup_related_threshold: float = 0.70
dedup_time_window_days: int = 7
dedup_log_all_similarities: bool = True  # For tuning
```

## References
- 구현: `app/agent/deduplication/event_matcher.py`
- 임베딩: sentence-transformers를 통한 BGE-M3
- 데이터베이스: pgvector 확장이 있는 PostgreSQL
- 임계값: `app/agent/config.py`
