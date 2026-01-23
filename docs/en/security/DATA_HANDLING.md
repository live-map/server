# Data Handling

How LiveMap processes and stores data.

---

## Data Flow

```
External Sources → Collection → Processing → Storage → Output
     │                │             │           │         │
   GDELT          Triggers      Verification   PostgreSQL  API
   Reddit         Scanner       Claim-level    pgvector    Feed
   USGS           Clustering    Generation                 JSON
```

---

## Data Categories

### Source Data

| Type | Retention | Storage |
|------|-----------|---------|
| Event metadata | 7 days | events table |
| Article content | Permanent | feeds table |
| Embeddings | Permanent | pgvector |

### Processing Data

| Type | Retention | Storage |
|------|-----------|---------|
| LLM responses | Not stored | Memory only |
| Intermediate claims | With article | JSONB in feeds |
| Verification results | With article | JSONB in feeds |

---

## Privacy Considerations

### No Personal Data Collection

LiveMap processes **publicly available news** and does not:
- Collect user personal data
- Track individual users
- Store cookies or identifiers
- Profile user behavior

### Source Attribution

All articles include:
- Source URLs
- Source names
- Confidence scores
- Verification methodology link

---

## Data Retention

### Default Policies

```python
# config.py
event_retention_days: int = 7      # Raw events
article_retention_days: int = -1    # Permanent (-1 = never delete)
```

### Cleanup Procedures

```sql
-- Manual cleanup of old events
DELETE FROM events
WHERE processed_at < NOW() - INTERVAL '7 days'
AND is_duplicate = true;
```

---

## External API Data

### GDELT

- Public domain data
- No authentication required
- Rate limited (respect limits)

### OpenAI

- Prompts sent to API
- Subject to OpenAI's data policy
- Not used for training (API usage)

### Reddit

- Public post data only
- No private messages or DMs
- Respects robots.txt

---

## Database Security

### Access Control

```sql
-- Restrict database access
GRANT SELECT, INSERT, UPDATE, DELETE ON feeds TO livemap_api;
GRANT SELECT, INSERT ON events TO livemap_api;
REVOKE ALL ON ALL TABLES FROM PUBLIC;
```

### Encryption

- **At rest**: Use PostgreSQL disk encryption
- **In transit**: Use SSL for database connections

```python
# Secure connection string
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/livemap?ssl=require
```

---

## Logging

### What We Log

- Event processing counts
- Error messages (no content)
- Performance metrics
- API response times

### What We Don't Log

- Full article content
- API keys
- User queries (if any)
- Source document bodies

### Log Example

```
10:06:47 | INFO | Scanner completed: 95 events processed
10:06:48 | INFO | Event verification: 35/168 passed
10:06:49 | INFO | Investigation started: event_id=123
```

---

## Compliance Notes

### GDPR (if applicable)

- No personal data processed
- Source data is public news
- No EU user data collected

### IFCN

- Methodology transparency
- Source attribution
- Corrections policy

---

## Related Documentation

- [API Keys](API_KEYS.md) - Credential security
- [Configuration](../guides/CONFIGURATION.md) - Settings
- [Database Schema](../reference/DATABASE_SCHEMA.md) - Data structure
