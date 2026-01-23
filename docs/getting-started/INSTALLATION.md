# Installation Guide

This guide provides detailed instructions for setting up the LiveMap backend for local development.

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Runtime |
| PostgreSQL | 15+ | Database |
| pgvector | 0.5+ | Vector similarity |
| Docker | 24+ | Container runtime |
| uv | latest | Package manager |

### API Keys

| API | Required | Purpose |
|-----|----------|---------|
| OpenAI | **Yes** | LLM for verification |
| Tavily | Optional | Web search |
| Reddit | Optional | Social media trigger |

---

## Step 1: Install Prerequisites

### macOS

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# Install pgvector
brew install pgvector

# Install Docker Desktop
brew install --cask docker

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Ubuntu/Debian

```bash
# Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# PostgreSQL 15
sudo apt install postgresql-15 postgresql-contrib-15

# pgvector
sudo apt install postgresql-15-pgvector

# Docker
sudo apt install docker.io docker-compose-v2
sudo usermod -aG docker $USER

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows (WSL2 recommended)

```powershell
# Install WSL2
wsl --install

# Then follow Ubuntu instructions inside WSL2
```

---

## Step 2: Database Setup

### Option A: Docker (Recommended)

```bash
cd backend

# Start PostgreSQL with pgvector
docker compose up -d db

# Verify
docker compose ps
# Should show: livemap-db running on port 5432
```

### Option B: Local PostgreSQL

```bash
# Create database and user
sudo -u postgres psql
```

```sql
CREATE USER livemap WITH PASSWORD 'livemap';
CREATE DATABASE livemap OWNER livemap;
\c livemap
CREATE EXTENSION vector;
\q
```

---

## Step 3: Project Setup

### Clone and Install Dependencies

```bash
cd livemap/backend

# Install Python dependencies
uv sync

# Verify installation
uv run python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
```

### Environment Configuration

```bash
# Copy example environment file
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required
OPENAI_API_KEY=sk-...

# Database (Docker default)
DATABASE_URL=postgresql+asyncpg://livemap:livemap@localhost:5432/livemap

# Optional: Search APIs
TAVILY_API_KEY=tvly-...

# Agent Settings
AGENT_GDELT_ENABLED=true
AGENT_REDDIT_ENABLED=true
AGENT_MIN_CONFIDENCE_SCORE=0.70
AGENT_EVENT_VERIFICATION_ENABLED=true
AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT=true
```

### Database Migration

```bash
# Run Alembic migrations
uv run alembic upgrade head

# Verify tables created
docker compose exec db psql -U livemap -d livemap -c "\dt"
```

---

## Step 4: Start the Server

### Development Mode

```bash
# Start with auto-reload
uv run uvicorn app.main:app --reload --port 8000
```

### Production Mode

```bash
# Start with multiple workers
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Step 5: Verify Installation

### Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"Livemap API"}
```

### API Documentation

Open in browser: http://localhost:8000/docs

### Test Scan

```bash
# Trigger a manual scan
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Common Issues

### "Module not found" errors

```bash
# Reinstall dependencies
uv sync --force-reinstall
```

### Database connection errors

```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# If using Docker
docker compose ps
docker compose logs db

# Restart database
docker compose restart db
```

### pgvector extension missing

```bash
# Docker
docker compose exec db psql -U livemap -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Local PostgreSQL
sudo -u postgres psql -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Zero-shot model loading slow

First run downloads the BART-MNLI model (~1.6GB). This is cached for subsequent runs.

```bash
# Pre-download model
uv run python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"
```

### OpenAI API errors

```bash
# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## Optional: Development Tools

### Pre-commit Hooks

```bash
uv run pre-commit install
```

### IDE Setup (VS Code)

Install extensions:
- Python
- Pylance
- Ruff

Add to `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "basic"
}
```

---

## Next Steps

- [First Scan Tutorial](FIRST_SCAN.md) - Run your first news scan
- [Project Structure](PROJECT_STRUCTURE.md) - Understand the codebase
- [Configuration Reference](../guides/CONFIGURATION.md) - All settings

---

*See [Troubleshooting](../guides/TROUBLESHOOTING.md) for more help*
