# Livemap Backend - Developer Guide

> Claim-Level Verification Agent v3 Codebase Guide

---

## Change History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-12 | Initial creation (Stage 0-3 pipeline) |
| 2.0 | 2026-01-13 | Legacy removal, rewritten focusing on agent system |
| 3.0 | 2026-01-14 | Claim-Level Verification v3 (2026 SOTA) implementation |
| **3.1** | **2026-01-14** | **Production-Ready quality improvements (stability, performance, code quality)** |

### v3.1 Quality Improvements (2026-01-14) ✅ NEW

**Why was this changed?**
- Fixed 15 issues through in-depth code quality analysis
- Achieved production-level stability

**Key Changes:**
1. **LLM Timeout**: 60-second timeout for all LLM calls
2. **Parallelization**: Parallel claim verification with `asyncio.gather()` + `Semaphore`
3. **Input Validation**: Minimum/maximum length validation
4. **Pydantic v2**: Migration to `model_config = ConfigDict(...)`
5. **Error Recovery**: Error recovery logic in scanner loop

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Project Structure](#2-project-structure)
3. [Core Concepts](#3-core-concepts)
4. [Agent System](#4-agent-system)
5. [Code Conventions](#5-code-conventions)
6. [Adding New Features](#6-adding-new-features)
7. [Testing](#7-testing)

---

## 1. Getting Started

### 1.1 Required Tools

```bash
# Install Python 3.11+
# Install Docker Desktop
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 1.2 Project Setup

```bash
cd backend
uv sync

# Start database
docker compose up -d db

# Set up environment variables
cp .env.example .env
# Set OPENAI_API_KEY in .env file

# Run DB migration
uv run alembic upgrade head

# Start server
uv run uvicorn app.main:app --reload --port 8000
```

### 1.3 Verification

```bash
curl http://localhost:8000/health
# {"status":"healthy","service":"Livemap API"}

open http://localhost:8000/docs
```

---

## 2. Project Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI entry point
│   │
│   ├── core/                      # Shared infrastructure
│   │   ├── config.py              # Environment variables (Settings)
│   │   ├── database.py            # SQLAlchemy session
│   │   └── lifespan.py            # App startup/shutdown (uses ClaimVerificationAgent)
│   │
│   ├── agent/                     # Autonomous agent system
│   │   ├── graph/
│   │   │   └── state.py           # LangGraph state definitions
│   │   ├── tools/
│   │   │   ├── __init__.py        # ALL_TOOLS export
│   │   │   ├── search.py          # GDELT, Tavily, ddgs
│   │   │   ├── social.py          # Telegram, YouTube
│   │   │   └── media.py           # Video download
│   │   ├── triggers/
│   │   │   ├── base.py            # TriggerEvent model
│   │   │   ├── gdelt.py           # GDELT trigger
│   │   │   ├── telegram.py        # Telegram trigger
│   │   │   └── manager.py         # TriggerManager (LLM classification)
│   │   ├── config.py              # Agent settings
│   │   ├── scanner.py             # NewsScanner
│   │   ├── claim_extraction.py    # ★ V3: VeriScore-style claim extraction
│   │   ├── qa_verifier.py         # ★ V3: QA-based LLM verification
│   │   ├── article_generator.py   # ★ V3: AP Style article generation
│   │   ├── investigator_v3.py     # ★ V3: Claim-Level Verification (current)
│   │   ├── investigator_v2.py     # V2: Deep Verification (legacy)
│   │   └── investigator.py        # V1: Basic agent (legacy)
│   │
│   ├── api/v1/
│   │   ├── routes/
│   │   │   ├── feeds.py           # Feed CRUD
│   │   │   └── agent.py           # Agent API
│   │   └── router.py              # Router registration
│   │
│   ├── models/
│   │   └── feed.py                # Feed model
│   │
│   └── schemas/
│       ├── feed.py
│       └── agent.py
│
├── alembic/                       # DB migrations
├── docs/                          # Documentation
└── pyproject.toml                 # Dependencies
```

---

## 3. Core Concepts

### 3.1 FastAPI Basic Patterns

**Router (Endpoint Definition)**

```python
# app/api/v1/routes/agent.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent import InvestigateRequest

router = APIRouter()

@router.post("/investigate")
async def investigate(
    request: InvestigateRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/v1/agent/investigate"""
    # Business logic
    return {"status": "started"}
```

**Dependency Injection**

```python
# app/core/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### 3.2 Pydantic Schemas

```python
# app/schemas/agent.py
from pydantic import BaseModel, Field

class InvestigateRequest(BaseModel):
    topic: str = Field(..., min_length=5, description="Topic to investigate")
    category: str = Field(default="general")

class InvestigateResponse(BaseModel):
    id: str
    status: str
    summary: str | None = None
```

### 3.3 SQLAlchemy Models

```python
# app/models/feed.py
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
```

### 3.4 Asynchronous Programming

```python
# Parallel execution (recommended)
results = await asyncio.gather(
    search_gdelt(query),
    search_duckduckgo(query),
    search_telegram(query),
)

# Sequential execution (slower)
result1 = await search_gdelt(query)
result2 = await search_duckduckgo(query)
```

---

## 4. Agent System

### 4.1 Claim-Level Verification Agent v3 (Currently in Use)

```python
# app/agent/investigator_v3.py

class ClaimVerificationAgent:
    """
    2026 SOTA-based 5-stage pipeline (AIC CTU + HerO 2 + VeriScore)

    Pipeline:
    1. EXTRACTOR: VeriScore-style atomic claim extraction
    2. RETRIEVER: Multi-source evidence collection (GDELT/DDG/Tavily)
    3. VERIFIER: QA-based LLM verification
    4. AGGREGATOR: Confidence-Weighted Voting
    5. SYNTHESIZER: AP Style article generation
    """

    def __init__(self, model: str | None = None):
        self.model = model or agent_settings.llm_model
        self.claim_extractor = ClaimExtractor(model=self.model)
        self.qa_verifier = QAVerifier(model=self.model)
        self.article_generator = ArticleGenerator(model=self.model)

    async def investigate(self, event: str, category: str) -> dict:
        # 1. Claim Extraction
        claims = await self.claim_extractor.extract(event)

        # 2. Evidence Retrieval (parallel)
        evidence = await self._gather_evidence(claims)

        # 3. QA Verification
        verdicts = await self.qa_verifier.verify_claims(claims, evidence)

        # 4. Aggregation
        aggregated = self._aggregate_verdicts(verdicts)

        # 5. Article Generation (AP Style)
        article = await self.article_generator.generate(event, verdicts)

        return {
            "claims": claims,
            "evidence_docs": evidence,
            "verdicts": verdicts,
            "article": article,
            **aggregated,
        }
```

### 4.2 Core Components

```python
# app/agent/claim_extraction.py
class ClaimExtractor:
    """VeriScore-style atomic claim extraction"""
    async def extract(self, text: str) -> ClaimExtractionResult

# app/agent/qa_verifier.py
class QAVerifier:
    """QA-based LLM verification (AIC CTU approach)"""
    async def verify_claim(self, claim, evidence_docs) -> ClaimVerdict
    async def verify_claims(self, claims, evidence_docs) -> VerificationResult

# app/agent/article_generator.py
class ArticleGenerator:
    """AP Style article generation (AP Stylebook 2024-2026 compliant)"""
    async def generate(self, event_summary, verification_result) -> GeneratedArticle
```

### 4.3 AgentConfig (v3.1 Update)

```python
# app/agent/config.py
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class AgentSettings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3

    # Search
    tavily_api_key: str = ""
    gdelt_enabled: bool = True

    # Scanner
    scan_interval_minutes: int = 15

    # ★ v3.1 NEW: Timeout and concurrency settings
    llm_timeout_seconds: float = 60.0
    max_concurrent_llm_calls: int = 3
    investigation_timeout_seconds: float = 300.0  # 5 minutes

    # Pydantic v2 configuration
    model_config = ConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        extra="ignore",
    )

# Singleton instance
agent_settings = AgentSettings()
```

### 4.4 V3Config (investigator_v3.py)

```python
class V3Config:
    """Configuration for Claim-Level Verification Agent."""

    # Claim extraction
    MAX_CLAIMS: int = 10

    # Evidence retrieval
    MAX_EVIDENCE_PER_CLAIM: int = 10
    MAX_TOTAL_EVIDENCE: int = 50

    # Rate limiting (from agent_settings)
    MAX_CONCURRENT_SEARCHES: int = 5
    MAX_CONCURRENT_LLM_CALLS: int = agent_settings.max_concurrent_llm_calls

    # Timeouts (seconds)
    TOOL_TIMEOUT: float = 30.0
    LLM_TIMEOUT: float = agent_settings.llm_timeout_seconds

    # Retry
    MAX_RETRIES: int = 3

    # ★ v3.1 NEW: Input validation
    MIN_INPUT_LENGTH: int = 10
    MAX_INPUT_LENGTH: int = 10000
```

### 4.5 Adding Tools

**Step 1: Define Tool Function**

```python
# app/agent/tools/search.py
from langchain_core.tools import tool

@tool
async def search_new_source(query: str, max_results: int = 10) -> list[dict]:
    """
    Search from a new source.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results
    """
    # Implementation
    results = await new_api.search(query, limit=max_results)
    return [{"title": r.title, "url": r.url, "content": r.content} for r in results]
```

**Step 2: Register in ALL_TOOLS**

```python
# app/agent/tools/__init__.py
from .search import search_new_source

ALL_TOOLS = [
    search_news_gdelt,
    search_web_free,
    search_new_source,  # Add new tool
    search_telegram,
    search_youtube,
    search_web,
]
```

### 4.6 Adding Triggers

```python
# app/agent/triggers/new_source.py
from .base import BaseTrigger, TriggerEvent, TriggerSource

class NewSourceTrigger(BaseTrigger):
    def __init__(self):
        self.api = NewSourceAPI()

    async def scan(self) -> list[TriggerEvent]:
        events = []
        items = await self.api.get_latest()

        for item in items:
            events.append(TriggerEvent(
                title=item.title,
                url=item.url,
                source=TriggerSource.NEW_SOURCE,
                published_at=item.published,
            ))

        return events
```

---

## 5. Code Conventions

### 5.1 Naming

```python
# Functions: snake_case, start with verb
async def search_news(query: str) -> list[dict]:
    pass

# Classes: PascalCase
class DeepVerificationAgent:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
TOOL_TIMEOUT = 30.0
```

### 5.2 Type Hints (Required)

```python
from typing import Any

def process(
    text: str,
    threshold: float = 0.5,
    options: list[str] | None = None,
) -> dict[str, Any]:
    ...
```

### 5.3 Error Handling

```python
import logging

logger = logging.getLogger(__name__)

async def search_with_retry(tool, args):
    try:
        result = await asyncio.wait_for(
            tool.ainvoke(args),
            timeout=30.0,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Tool timeout", extra={"tool": tool.name})
        return {"error": "timeout"}
    except Exception as e:
        logger.error("Tool error", extra={"tool": tool.name, "error": str(e)})
        return {"error": str(e)}
```

### 5.4 Logging

```python
# Structured logging recommended
logger.info(
    "Research complete",
    extra={
        "subtopic_count": len(subtopics),
        "sources": len(sources),
        "execution_time": elapsed,
    },
)

# Avoid: using print()
# print(f"Research complete: {len(subtopics)} subtopics")  # ❌
```

---

## 6. Adding New Features

### 6.1 New API Endpoint

**Step 1: Define Schema**

```python
# app/schemas/example.py
from pydantic import BaseModel

class ExampleRequest(BaseModel):
    text: str

class ExampleResponse(BaseModel):
    result: str
```

**Step 2: Create Router**

```python
# app/api/v1/routes/example.py
from fastapi import APIRouter

router = APIRouter()

@router.post("", response_model=ExampleResponse)
async def process_example(request: ExampleRequest):
    return ExampleResponse(result="done")
```

**Step 3: Register Router**

```python
# app/api/v1/router.py
from app.api.v1.routes import example

api_router.include_router(
    example.router,
    prefix="/example",
    tags=["example"],
)
```

### 6.2 New DB Table

**Step 1: Define Model**

```python
# app/models/example.py
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Example(Base):
    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

**Step 2: Migration**

```bash
uv run alembic revision --autogenerate -m "Add example table"
uv run alembic upgrade head
```

---

## 7. Testing

### 7.1 Running Tests

```bash
# Run all tests
uv run pytest

# Specific file
uv run pytest tests/test_agent.py -v

# Specific test
uv run pytest tests/test_agent.py::test_investigate -v
```

### 7.2 Writing Tests

```python
# tests/test_agent.py
import pytest
from app.agent.investigator_v2 import DeepVerificationAgent

@pytest.mark.asyncio
async def test_investigate():
    agent = DeepVerificationAgent()
    result = await agent.investigate(
        event="Test event",
        category="test"
    )
    assert result.event_summary is not None
```

---

## Appendix: Useful Commands

```bash
# Start server
uv run uvicorn app.main:app --reload --port 8000

# Migration
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1

# Testing
uv run pytest -v

# DB connection
docker exec -it livemap-db psql -U livemap -d livemap
```

---

## References

### Official Documentation

| Technology | Documentation |
|------------|---------------|
| FastAPI | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| Pydantic v2 | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| SQLAlchemy 2.0 | [docs.sqlalchemy.org](https://docs.sqlalchemy.org/) |
| LangGraph | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/) |
| tenacity | [tenacity.readthedocs.io](https://tenacity.readthedocs.io/) |

### Best Practices

| Topic | Link |
|-------|------|
| FastAPI Best Practices | [github.com/zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) |
| LangGraph Production Template | [github.com/wassim249/fastapi-langgraph-agent-production-ready-template](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template) |

### 2026 SOTA Research

| Research | Link |
|----------|------|
| AIC CTU (FEVER 8 Winner) | [arxiv.org/html/2508.04390](https://arxiv.org/html/2508.04390) |
| HerO 2 (AVeriTeC 2025) | [arxiv.org/html/2507.11004](https://arxiv.org/html/2507.11004) |
| MedRAGChecker (2026) | [arxiv.org/html/2601.06519](https://arxiv.org/html/2601.06519) |
| Claim Verification Survey | [arxiv.org/html/2408.14317v2](https://arxiv.org/html/2408.14317v2) |
| VeriScore | [github.com/Yixiao-Song/VeriScore](https://github.com/Yixiao-Song/VeriScore) |
| AP Stylebook 2024-2026 | [Amazon](https://www.amazon.com/Associated-Press-Stylebook-2024-2026/dp/154160511X) |

---

*Last updated: 2026-01-14*
*Version: 3.1 (Production-Ready Claim-Level Verification)*
