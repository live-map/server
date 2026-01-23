# Deduplication Algorithm

## Overview

2계층 중복 제거 시스템은 중복 및 관련 이벤트를 식별하여 불필요한 처리와 저장을 방지합니다.

## Architecture

```
Input: Event text + embedding
  ↓
Layer 1: Hash Match (O(1), exact)
  ├─ Match found → EXACT duplicate
  ↓ No match
Layer 2: Semantic Search (pgvector)
  ├─ sim >= 0.95 → DUPLICATE
  ├─ sim 0.85-0.95 → POTENTIAL (LLM verify)
  ├─ sim 0.70-0.85 → RELATED (link)
  └─ sim < 0.70 → NEW event
```

## Layer 1: Hash Matching

### Purpose
O(1) 시간 내에 정확히 일치하는 중복을 찾습니다.

### Hash Generation

```python
def _generate_hash(text: str) -> str:
    # 1. Lowercase
    normalized = text.lower().strip()

    # 2. Remove punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)

    # 3. Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized)

    # 4. SHA-256 hash
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
```

### Properties
- **Deterministic:** 동일한 텍스트는 항상 동일한 해시를 생성
- **Case-insensitive:** "Attack" == "attack"
- **Punctuation-insensitive:** "Attack!" == "Attack"
- **Whitespace-normalized:** "Attack  now" == "Attack now"

### Database Lookup
```sql
SELECT * FROM events
WHERE event_hash = :hash AND is_active = true
```

## Layer 2: Semantic Search

### Purpose
벡터 유사도를 사용하여 의미적으로 유사한 이벤트를 찾습니다.

### Embedding Model
- **Model:** BGE-M3 (BAAI/bge-m3)
- **Dimensions:** 1024
- **Distance metric:** Cosine

### pgvector Query

```sql
SELECT
    id,
    canonical_title,
    1 - (embedding <=> :query_embedding) as similarity
FROM events
WHERE
    is_active = true
    AND created_at >= :cutoff_date
    AND embedding IS NOT NULL
    AND (embedding <=> :query_embedding) <= :max_distance
ORDER BY embedding <=> :query_embedding
LIMIT 1
```

**Note:** pgvector는 코사인 거리에 `<=>`를 사용합니다. 유사도 = 1 - 거리.

## Threshold Classification

| Similarity | Match Type | Action |
|------------|------------|--------|
| 1.00 | EXACT | 건너뛰기 (해시 매치) |
| >= 0.95 | DUPLICATE | 건너뛰기 |
| 0.85 - 0.95 | POTENTIAL | LLM 검증 |
| 0.70 - 0.85 | RELATED | 스토리 체인으로 연결 |
| < 0.70 | NEW | 새 이벤트 생성 |

### DUPLICATE (>= 0.95)
- 거의 동일한 콘텐츠
- 다른 표현, 동일한 사실
- 중복 방지를 위해 건너뛰기

### POTENTIAL (0.85 - 0.95)
- 동일한 이벤트일 가능성이 높으나 일부 차이 존재
- 새로운 정보가 포함된 업데이트일 수 있음
- 중복인지 업데이트인지 LLM 판단 필요

### RELATED (0.70 - 0.85)
- 동일한 주제, 다른 이벤트
- 진행 중인 스토리의 일부
- 맥락을 위해 연결하되 병합하지 않음

### NEW (< 0.70)
- 다른 이벤트
- 새 항목으로 생성

## Match Result

```python
@dataclass
class MatchResult:
    match_type: MatchType  # EXACT, DUPLICATE, POTENTIAL, RELATED, NEW
    matched_event_id: int | None
    similarity_score: float | None
    matched_event: Event | None

    @property
    def is_duplicate(self) -> bool:
        return self.match_type in (MatchType.EXACT, MatchType.DUPLICATE)

    @property
    def is_potential_match(self) -> bool:
        return self.match_type == MatchType.POTENTIAL
```

## Usage

```python
matcher = EventMatcher(db_session)

# With embedding (full matching)
result = await matcher.find_match(
    event_text="Iran attacks US bases",
    embedding=embedding_vector,
    category="military"
)

if result.is_duplicate:
    logger.info("Skipping duplicate event")
elif result.is_potential_match:
    # Use LLM to determine if update or duplicate
    is_update = await verify_with_llm(event_text, result.matched_event)
else:
    # Create new event
    create_event(event_text)
```

## Fact Hash (Update Detection)

이벤트가 업데이트인지 감지하기 위해 팩트 해시를 비교합니다:

```python
def generate_fact_hash(facts: list[str]) -> str:
    # Sort for order-independence
    normalized_facts = sorted([
        re.sub(r'\s+', ' ', f.lower().strip())
        for f in facts
    ])
    combined = '|'.join(normalized_facts)
    return hashlib.sha256(combined.encode()).hexdigest()
```

팩트 해시가 다르면 새 이벤트에 새로운 정보가 포함되어 있습니다(업데이트).

## Configuration

```python
# In agent_settings
dedup_duplicate_threshold: float = 0.95
dedup_potential_threshold: float = 0.85
dedup_related_threshold: float = 0.70
dedup_time_window_days: int = 7
dedup_log_all_similarities: bool = True  # For tuning
```

## Performance

| Operation | Complexity | Latency |
|-----------|------------|---------|
| Hash lookup | O(1) | ~1ms |
| Embedding generation | O(n) | ~100ms |
| Vector search | O(log n) | ~10ms |

## Database Schema

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_hash VARCHAR(64) NOT NULL,
    canonical_title TEXT NOT NULL,
    embedding vector(1024),
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookup
CREATE INDEX idx_event_hash ON events(event_hash);
CREATE INDEX idx_embedding ON events
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

## File Location

```
app/agent/deduplication/event_matcher.py
```

## Related Documentation
- [Cross-Source Matcher](CROSS_SOURCE_MATCHER.md)
- [ADR-006: Deduplication](../adr/ADR-006-deduplication.md)
