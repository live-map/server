# Getting Started with LiveMap Backend

This guide will help you set up the LiveMap backend for local development in about 5 minutes.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- OpenAI API key
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Setup

### 1. Clone and Install Dependencies

```bash
cd livemap/backend
uv sync
```

### 2. Set Up Environment Variables

Create `.env` file:

```bash
# Required
OPENAI_API_KEY=sk-...

# Database (default: PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/livemap

# Optional: Agent settings
AGENT_GDELT_ENABLED=true
AGENT_REDDIT_ENABLED=true
AGENT_MIN_CONFIDENCE_SCORE=0.70
```

### 3. Start the Server

```bash
uv run uvicorn app.main:app --reload
```

Server runs at http://localhost:8000

### 4. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Trigger a scan
curl -X POST http://localhost:8000/api/v1/agent/scan
```

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── core/                # Configuration, database, lifespan
├── api/v1/              # API routes (agent, feeds)
├── agent/               # News intelligence agent
│   ├── scanner.py       # Multi-source scanner
│   ├── event_verifier.py # Gate 0: Event verification
│   ├── confidence_scorer.py # Confidence scoring
│   ├── cross_source_matcher.py # Source matching
│   ├── triggers/        # Data source connectors
│   └── deduplication/   # Event deduplication
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic validation schemas
└── services/            # Business logic layer
```

## Key Concepts

### 7-Stage Pipeline

1. **Trigger Collection** - Gather events from multiple sources
2. **Clustering** - Group similar events
3. **Source Classification** - Tier-based source categorization
4. **Event Verification (Gate 0)** - Filter non-events
5. **Confidence Scoring** - Calculate multi-source confidence
6. **Content Gates** - Filter entertainment, speculation
7. **Final Output** - Category limiting, formatting

### Source Tiers

| Tier | Sources | Credibility |
|------|---------|-------------|
| Tier-1 | USGS, NOAA, GDELT | 0.90-0.99 |
| Tier-2 | Currents, WorldNews | 0.75-0.85 |
| Tier-3 | Reddit, Twitter | 0.30-0.40 |

### Two-Source Rule

Events require verification from 2+ independent sources before publication (exception: Tier-1 government sources).

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/unit/test_event_verifier.py -v

# With coverage
uv run pytest tests/ --cov=app --cov-report=html
```

## Common Tasks

### Triggering a Manual Scan

```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Starting an Investigation

```bash
curl -X POST http://localhost:8000/api/v1/agent/investigate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Iran attacks US bases in Iraq"}'
```

### Checking Scanner Status

```bash
curl http://localhost:8000/api/v1/agent/status
```

## Configuration Reference

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | Required for LLM features |
| `AGENT_GDELT_ENABLED` | true | Enable GDELT news source |
| `AGENT_REDDIT_ENABLED` | true | Enable Reddit source |
| `AGENT_MIN_CONFIDENCE_SCORE` | 0.70 | Publication threshold |
| `AGENT_EVENT_VERIFICATION_ENABLED` | true | Enable Gate 0 |
| `AGENT_SCAN_INTERVAL_MINUTES` | 15 | Scan frequency |

See `app/agent/config.py` for full configuration options.

## Troubleshooting

### "Module not found" errors
```bash
uv sync  # Reinstall dependencies
```

### Database connection errors
```bash
# Ensure PostgreSQL is running
pg_isready -h localhost -p 5432

# Check pgvector extension
psql -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### No events returned from scan
- Check if sources are enabled in `.env`
- Verify GDELT is accessible: `curl "https://api.gdeltproject.org/api/v2/doc/doc"`
- Lower `MIN_CONFIDENCE_SCORE` for testing

## Next Steps

- Read [METHODOLOGY.md](METHODOLOGY.md) for system design
- Explore [API Reference](api/README.md) for endpoints
- Check [Architecture Decisions](adr/README.md) for design rationale
- Review [Trigger Guide](guides/TRIGGER_GUIDE.md) to add new sources
