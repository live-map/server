# Troubleshooting Guide

Common issues and solutions for LiveMap.

---

## Quick Diagnostics

```bash
# Check server health
curl http://localhost:8000/health

# Check agent status
curl http://localhost:8000/api/v1/agent/status

# View recent logs
docker compose logs --tail=100 api
```

---

## Installation Issues

### "Module not found" errors

**Symptom**: Import errors when starting the server

**Solution**:
```bash
# Reinstall all dependencies
uv sync --force-reinstall

# If specific package missing
uv add <package-name>
```

### Python version mismatch

**Symptom**: Syntax errors or import failures

**Solution**:
```bash
# Check Python version
python --version  # Should be 3.11+

# Use specific Python version
uv python pin 3.11
uv sync
```

---

## Database Issues

### Connection refused

**Symptom**: `psycopg.OperationalError: connection refused`

**Solution**:
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# If using Docker
docker compose ps
docker compose up -d db

# Check connection string
echo $DATABASE_URL
```

### pgvector extension missing

**Symptom**: `extension "vector" does not exist`

**Solution**:
```bash
# Docker
docker compose exec db psql -U livemap -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Local PostgreSQL
sudo apt install postgresql-15-pgvector
sudo -u postgres psql -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Migration errors

**Symptom**: Alembic migration failures

**Solution**:
```bash
# Check current migration state
uv run alembic current

# Reset to specific version
uv run alembic downgrade -1
uv run alembic upgrade head

# If completely broken, reset (CAUTION: data loss)
uv run alembic stamp head
```

---

## API Issues

### OpenAI API errors

**Symptom**: `openai.AuthenticationError` or rate limits

**Solution**:
```bash
# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check rate limits (in .env)
AGENT_MAX_CONCURRENT_LLM_CALLS=3
AGENT_LLM_TIMEOUT_SECONDS=60
```

### 429 Too Many Requests (GDELT)

**Symptom**: GDELT trigger returns rate limit errors

**Solution**:
```bash
# Increase scan interval
AGENT_SCAN_INTERVAL_MINUTES=30  # instead of 15

# Or add delay between GDELT calls
AGENT_GDELT_DELAY_SECONDS=5
```

---

## Scanner Issues

### No events collected

**Symptom**: Scanner runs but returns 0 events

**Checklist**:
```bash
# 1. Check source enabled
echo $AGENT_GDELT_ENABLED  # should be true

# 2. Check GDELT API directly
curl "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&maxrecords=10"

# 3. Check logs for errors
docker compose logs api | grep -i "error\|exception"
```

### Events filtered but no articles generated

**Symptom**: Events pass filters but no articles in DB

**Checklist**:
```bash
# 1. Check for duplicates
# Look for "SKIPPING: Duplicate event" in logs

# 2. Check investigation limit
echo $AGENT_MAX_INVESTIGATIONS  # default is 3

# 3. Check LLM timeout
echo $AGENT_LLM_TIMEOUT_SECONDS  # default is 60
```

### Gate 0 rejecting too many events

**Symptom**: High rejection rate in event verification

**Diagnosis**:
```bash
# Check logs for rejection reasons
docker compose logs api | grep "GATE0-REJECT"

# Common patterns:
# [GATE0-REJECT] NOT_EVENT: pattern 'movie' matched
# [GATE0-REJECT] ZERO_SHOT: sports (0.92)
```

**Solutions**:
- Adjust pattern matching in `event_verifier.py`
- Lower zero-shot confidence threshold
- Check if keywords are too broad

---

## Performance Issues

### Slow embedding generation

**Symptom**: Clustering takes > 10 seconds

**Solutions**:
```bash
# 1. Pre-download model
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# 2. Reduce batch size
AGENT_EMBEDDING_BATCH_SIZE=32

# 3. Use GPU (if available)
CUDA_VISIBLE_DEVICES=0 uv run uvicorn app.main:app --reload
```

### Zero-shot model loading slow

**Symptom**: First request takes 30+ seconds

**Solution**:
```bash
# Pre-download BART-MNLI model
uv run python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"

# Model is cached in ~/.cache/huggingface/
```

### Memory issues

**Symptom**: OOM errors or slow performance

**Solutions**:
```bash
# 1. Limit embedding batch size
AGENT_MAX_EVENTS_PER_SCAN=100

# 2. Reduce concurrent LLM calls
AGENT_MAX_CONCURRENT_LLM_CALLS=2

# 3. Add swap (if on limited RAM)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Docker Issues

### Container won't start

**Symptom**: Container exits immediately

**Diagnosis**:
```bash
# Check exit reason
docker compose logs api

# Common causes:
# - Missing environment variables
# - Port already in use
# - Database not ready
```

### Network issues between containers

**Symptom**: API can't reach database

**Solution**:
```bash
# Check network
docker network ls
docker network inspect livemap_default

# Ensure services on same network
docker compose down
docker compose up -d
```

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `OPENAI_API_KEY not set` | Missing API key | Add to .env file |
| `Connection refused: 5432` | DB not running | Start PostgreSQL |
| `extension "vector" does not exist` | pgvector missing | Install extension |
| `Too many requests (429)` | Rate limited | Reduce scan frequency |
| `Timeout waiting for response` | LLM slow/overloaded | Increase timeout |
| `No module named 'xxx'` | Missing dependency | Run `uv sync` |

---

## Getting Help

### Collecting Debug Information

```bash
# Create debug report
echo "=== Environment ===" > debug.txt
python --version >> debug.txt
uv --version >> debug.txt
docker --version >> debug.txt

echo "=== Configuration ===" >> debug.txt
cat .env | grep -v KEY >> debug.txt

echo "=== Recent Logs ===" >> debug.txt
docker compose logs --tail=200 api >> debug.txt

echo "=== Database ===" >> debug.txt
docker compose exec db psql -U livemap -c "\dt" >> debug.txt
```

### Reporting Issues

When reporting issues, include:
1. Error message (full traceback)
2. Steps to reproduce
3. Environment details (OS, Python version)
4. Configuration (without API keys)
5. Recent logs

---

## Related Documentation

- [Installation](../getting-started/INSTALLATION.md) - Setup guide
- [Configuration](CONFIGURATION.md) - All settings
- [Architecture](../architecture/README.md) - System design
