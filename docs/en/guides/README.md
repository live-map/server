# How-To Guides

Practical guides for common development tasks.

---

## Available Guides

### Setup & Configuration
- **[Configuration Reference](CONFIGURATION.md)** - All environment variables and settings

### Development
- **[Trigger Guide](TRIGGER_GUIDE.md)** - Adding new data sources
- **[Testing Guide](TESTING_GUIDE.md)** - Running and writing tests

### Operations
- **[Deployment](DEPLOYMENT.md)** - Production deployment options
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

---

## Quick Start Tasks

### Run the Server

```bash
# Development
uv run uvicorn app.main:app --reload --port 8000

# Production
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Run Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/unit/test_event_verifier.py -v

# With coverage
uv run pytest tests/ --cov=app --cov-report=html
```

### Trigger a Scan

```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Check Status

```bash
curl http://localhost:8000/api/v1/agent/status
```

### Database Migration

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Add new field"

# Apply migrations
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

---

## Common Recipes

### Add a New Trigger Source

1. Create trigger class in `app/agent/triggers/`
2. Implement `scan()` method returning `list[TriggerEvent]`
3. Register in `TriggerManager`
4. Add configuration in `config.py`

See [Trigger Guide](TRIGGER_GUIDE.md) for details.

### Add a New API Endpoint

1. Define Pydantic schemas in `app/schemas/`
2. Create route in `app/api/v1/routes/`
3. Register router in `app/api/v1/router.py`

### Debug Event Filtering

```bash
# Watch Gate 0 rejections
docker compose logs api | grep "GATE0-REJECT"

# Watch confidence scoring
docker compose logs api | grep "CONFIDENCE"
```

---

## Related Documentation

- [Getting Started](../getting-started/README.md) - Initial setup
- [Architecture](../architecture/README.md) - System design
- [API Reference](../api/README.md) - Endpoint documentation
