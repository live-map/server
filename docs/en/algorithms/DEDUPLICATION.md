# Deduplication Algorithm

## Overview

The two-layer deduplication system identifies duplicate and related events to prevent redundant processing and storage.

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
Catch exact duplicates in O(1) time.

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
- **Deterministic:** Same text always produces same hash
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
Find semantically similar events using vector similarity.

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

**Note:** pgvector uses `<=>` for cosine distance. Similarity = 1 - distance.

## Threshold Classification

| Similarity | Match Type | Action |
|------------|------------|--------|
| 1.00 | EXACT | Skip (hash match) |
| >= 0.95 | DUPLICATE | Skip |
| 0.85 - 0.95 | POTENTIAL | LLM verification |
| 0.70 - 0.85 | RELATED | Link as story chain |
| < 0.70 | NEW | Create new event |

### DUPLICATE (>= 0.95)
- Nearly identical content
- Different wording, same facts
- Skip to avoid redundancy

### POTENTIAL (0.85 - 0.95)
- Likely same event, some differences
- Could be update with new information
- Requires LLM to determine if duplicate or update

### RELATED (0.70 - 0.85)
- Same topic, different events
- Part of ongoing story
- Link for context, don't merge

### NEW (< 0.70)
- Different event
- Create as new entry

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

For detecting if an event is an update, compare fact hashes:

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

If fact hashes differ, the new event contains new information (update).

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
