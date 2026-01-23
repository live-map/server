# Cross-Source Matcher Algorithm

## Overview

The Cross-Source Matcher identifies the same news event reported by different sources. This enables:
- Multi-source verification (Two-Source Rule)
- Confidence score boosting
- Event clustering and deduplication

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

Events are filtered to a configurable time window (default: 6 hours).

```python
cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)
recent_events = [e for e in events if e.detected_at >= cutoff]
```

**Rationale:** News about the same event typically appears within hours. Older events are unlikely to be related to new reports.

## Step 2: Embedding Generation

Each event is converted to a 1024-dimensional vector using BGE-M3.

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
- **Normalization:** L2-normalized for cosine similarity

```python
embeddings = encoder.encode(
    texts,
    normalize_embeddings=True,
    show_progress_bar=False,
)
```

### Fallback
If embedding model unavailable, falls back to Jaccard similarity:

```python
def _text_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0
```

## Step 3: Similarity Matrix

Compute pairwise cosine similarity between all events.

```python
# With normalized embeddings, dot product = cosine similarity
similarity_matrix = np.dot(embeddings, embeddings.T)
```

**Result:** N×N matrix where `matrix[i][j]` is similarity between events i and j.

## Step 4: Cross-Source Matching

Find matches based on similarity threshold with source constraint.

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

**Key Rule:** Events from the same source are never matched together. This prevents:
- Counting duplicate articles from same outlet
- Self-verification (source can't verify itself)

## Step 5: MatchedEvent Creation

Group matched events into MatchedEvent objects.

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
    similarity_threshold=0.70,  # Minimum similarity for match
    time_window_hours=6,        # Events within this window
    embedding_model="BAAI/bge-m3"  # Embedding model
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

**Input Events:**
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

**Output:**
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
