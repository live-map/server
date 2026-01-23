# Database Schema

LiveMap은 벡터 유사도 검색을 위해 pgvector를 포함한 PostgreSQL을 사용합니다.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATABASE SCHEMA                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  feeds                     메인 기사 테이블                              │
│  ├── id                    기본 키                                       │
│  ├── title_ko, title_en    이중 언어 제목                                │
│  ├── content_ko, content_en 이중 언어 본문                               │
│  ├── category              이벤트 카테고리                               │
│  ├── confidence_score      신뢰도 점수 (0-1)                            │
│  ├── sources               소스 JSON 배열                                │
│  ├── embedding             벡터 (1024차원, pgvector)                     │
│  └── created_at            타임스탬프                                    │
│                                                                         │
│  events                    트리거로부터의 원시 이벤트                     │
│  ├── id                    기본 키                                       │
│  ├── title                 이벤트 제목                                   │
│  ├── source                트리거 소스 (gdelt, reddit 등)                │
│  ├── embedding             중복 제거용 벡터                              │
│  └── processed_at          처리 타임스탬프                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tables

### feeds

검증되고 게시된 뉴스를 저장하는 메인 기사 테이블입니다.

```sql
CREATE TABLE feeds (
    id SERIAL PRIMARY KEY,
    title_ko VARCHAR(500) NOT NULL,
    title_en VARCHAR(500) NOT NULL,
    content_ko TEXT NOT NULL,
    content_en TEXT NOT NULL,
    summary_ko TEXT,
    summary_en TEXT,
    category VARCHAR(50) NOT NULL,
    confidence_score FLOAT NOT NULL,
    confidence_level VARCHAR(20),
    sources JSONB NOT NULL DEFAULT '[]',
    two_source_satisfied BOOLEAN DEFAULT FALSE,
    original_event TEXT,
    claims JSONB,
    verdicts JSONB,
    embedding VECTOR(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_feeds_category ON feeds(category);
CREATE INDEX idx_feeds_created_at ON feeds(created_at DESC);
CREATE INDEX idx_feeds_confidence ON feeds(confidence_score DESC);
CREATE INDEX idx_feeds_embedding ON feeds USING ivfflat (embedding vector_cosine_ops);
```

### events

트리거 소스로부터의 원시 이벤트로, 중복 제거에 사용됩니다.

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    source VARCHAR(50) NOT NULL,
    source_url VARCHAR(1000),
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    embedding VECTOR(1024),
    cluster_id VARCHAR(50),
    is_duplicate BOOLEAN DEFAULT FALSE,
    feed_id INTEGER REFERENCES feeds(id)
);

-- Indexes
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_detected_at ON events(detected_at DESC);
CREATE INDEX idx_events_embedding ON events USING ivfflat (embedding vector_cosine_ops);
```

---

## SQLAlchemy Models

### Feed Model

```python
# app/models/feed.py
from sqlalchemy import Integer, String, Text, Float, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base

class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Bilingual content
    title_ko: Mapped[str] = mapped_column(String(500), nullable=False)
    title_en: Mapped[str] = mapped_column(String(500), nullable=False)
    content_ko: Mapped[str] = mapped_column(Text, nullable=False)
    content_en: Mapped[str] = mapped_column(Text, nullable=False)
    summary_ko: Mapped[str | None] = mapped_column(Text)
    summary_en: Mapped[str | None] = mapped_column(Text)

    # Classification
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    # Confidence
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_level: Mapped[str | None] = mapped_column(String(20))
    two_source_satisfied: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sources
    sources: Mapped[dict] = mapped_column(JSONB, default=list)

    # Original data
    original_event: Mapped[str | None] = mapped_column(Text)
    claims: Mapped[dict | None] = mapped_column(JSONB)
    verdicts: Mapped[dict | None] = mapped_column(JSONB)

    # Vector for similarity
    embedding: Mapped[list | None] = mapped_column(Vector(1024))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

### Event Model

```python
# app/models/event.py
from sqlalchemy import Integer, String, Text, Boolean, TIMESTAMP, ForeignKey
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )
    embedding: Mapped[list | None] = mapped_column(Vector(1024))
    cluster_id: Mapped[str | None] = mapped_column(String(50))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    feed_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeds.id")
    )
```

---

## JSONB Structures

### sources (feeds 테이블)

```json
[
  {
    "name": "gdelt",
    "tier": "tier1_news",
    "url": "https://...",
    "title": "Original article title"
  },
  {
    "name": "reddit",
    "tier": "tier3_social",
    "url": "https://reddit.com/r/worldnews/...",
    "title": "Post title"
  }
]
```

### claims (feeds 테이블)

```json
{
  "claims": [
    {
      "id": "claim_1",
      "text": "Iran launched ballistic missiles",
      "atomic": true
    },
    {
      "id": "claim_2",
      "text": "3 US soldiers were injured",
      "atomic": true
    }
  ],
  "extraction_model": "gpt-4o-mini",
  "extraction_time": "2026-01-23T10:00:00Z"
}
```

### verdicts (feeds 테이블)

```json
{
  "verdicts": [
    {
      "claim_id": "claim_1",
      "verdict": "SUPPORTED",
      "confidence": 0.92,
      "evidence": [
        {"source": "Reuters", "excerpt": "..."}
      ]
    },
    {
      "claim_id": "claim_2",
      "verdict": "NOT_ENOUGH_INFORMATION",
      "confidence": 0.65,
      "evidence": []
    }
  ],
  "aggregated_verdict": "MOSTLY_SUPPORTED",
  "supported_ratio": 0.75
}
```

---

## Vector Search

### Similarity Query

```python
from sqlalchemy import select
from pgvector.sqlalchemy import Vector

# Find similar events
query = (
    select(Event)
    .order_by(Event.embedding.cosine_distance(query_embedding))
    .limit(10)
)
results = await session.execute(query)
```

### Deduplication Query

```python
# Check if event is duplicate (similarity > 0.85)
query = (
    select(Event)
    .where(Event.embedding.cosine_distance(new_embedding) < 0.15)  # 1 - 0.85
    .limit(1)
)
```

---

## Migrations

### Create New Migration

```bash
uv run alembic revision --autogenerate -m "Add new field"
```

### Run Migrations

```bash
# Upgrade to latest
uv run alembic upgrade head

# Downgrade one step
uv run alembic downgrade -1

# Show current version
uv run alembic current
```

---

## Maintenance

### Index Rebuilding

```sql
-- Rebuild vector index for better performance
REINDEX INDEX idx_feeds_embedding;
REINDEX INDEX idx_events_embedding;
```

### Cleanup Old Events

```sql
-- Delete events older than 7 days (keep feeds)
DELETE FROM events
WHERE processed_at < NOW() - INTERVAL '7 days';
```

### Vacuum

```sql
-- Reclaim space after large deletes
VACUUM ANALYZE feeds;
VACUUM ANALYZE events;
```

---

## Related Documentation

- [Architecture](../architecture/README.md) - 시스템 설계
- [Deduplication](../algorithms/DEDUPLICATION.md) - 중복 제거 알고리즘
