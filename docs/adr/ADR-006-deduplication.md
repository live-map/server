# ADR-006: Two-Layer Deduplication

## Status
Accepted

## Context

High-volume news aggregation from multiple sources creates significant duplication:
- Same story reported by different outlets
- Minor rewording of identical events
- Updates to existing stories
- Related but distinct events

Without deduplication:
- Database bloat
- Redundant processing
- Poor user experience
- Wasted resources

We needed a system that:
1. Catches exact duplicates quickly
2. Identifies semantic duplicates (same meaning, different words)
3. Distinguishes updates from duplicates
4. Links related events

## Decision

Implement a **two-layer deduplication system**:

### Layer 1: Hash Matching (O(1), Exact)

Fast exact-match using normalized text hashing:

```python
def _generate_hash(text: str) -> str:
    # Normalize: lowercase, remove punctuation, collapse whitespace
    normalized = text.lower().strip()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)

    # SHA-256 hash
    return hashlib.sha256(normalized.encode()).hexdigest()
```

**Characteristics:**
- O(1) lookup via database index
- Zero false positives
- Catches exact reposts

### Layer 2: Semantic Search (pgvector, Similar)

Vector similarity for semantic matching:

```python
# Using BGE-M3 embeddings (1024 dimensions)
# Cosine similarity via pgvector

SELECT id, 1 - (embedding <=> query_embedding) as similarity
FROM events
WHERE (embedding <=> query_embedding) <= (1 - 0.70)
ORDER BY embedding <=> query_embedding
LIMIT 1
```

**Similarity Thresholds:**

| Similarity | Match Type | Action |
|------------|------------|--------|
| 1.00 | EXACT | Skip (hash match) |
| >= 0.95 | DUPLICATE | Skip |
| 0.85 - 0.95 | POTENTIAL | LLM verification |
| 0.70 - 0.85 | RELATED | Link as story chain |
| < 0.70 | NEW | Create new event |

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
- **Fast exact matching**: Hash lookup is O(1)
- **Semantic understanding**: Catches paraphrased duplicates
- **Graduated response**: Different actions for different similarity levels
- **Story linking**: Related events connected
- **Configurable thresholds**: Tunable per use case
- **Update detection**: Potential matches can be updates

### Negative
- **Embedding cost**: Each event needs embedding generation
- **Storage overhead**: 1024-dim vectors per event
- **Threshold tuning**: Requires empirical adjustment
- **pgvector dependency**: Specialized database extension
- **Potential false negatives**: Low similarity threshold might miss duplicates

## Alternatives Considered

### Alternative A: Hash-Only Deduplication
Use only exact hash matching.

**Rejected because:**
- Misses semantically identical content
- Paraphrased duplicates slip through
- High false negative rate

### Alternative B: LLM-Only Comparison
Use LLM to compare every pair of events.

**Rejected because:**
- O(n²) comparisons
- Extremely expensive at scale
- Slow (hundreds of ms per comparison)
- Overkill for most cases

### Alternative C: TF-IDF Similarity
Use traditional text similarity (TF-IDF, BM25).

**Rejected because:**
- No semantic understanding
- Keyword-based only
- Poor on paraphrased content
- Worse accuracy than embeddings

### Alternative D: Bloom Filter Pre-Check
Add bloom filter before hash check.

**Considered for future:**
- Could reduce hash lookups
- Probabilistic, adds complexity
- Current volume doesn't require it

## Implementation Details

### Embedding Model
- Model: BGE-M3 (BAAI/bge-m3)
- Dimensions: 1024
- Why: Multilingual, good balance of quality/size

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
- Implementation: `app/agent/deduplication/event_matcher.py`
- Embedding: BGE-M3 via sentence-transformers
- Database: PostgreSQL with pgvector extension
- Thresholds: `app/agent/config.py`
