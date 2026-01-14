# Livemap Backend - 개발자 가이드

> Claim-Level Verification Agent v3 기반 코드베이스 가이드

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2026-01-12 | 초기 작성 (Stage 0-3 파이프라인) |
| 2.0 | 2026-01-13 | 레거시 제거, 에이전트 시스템 중심으로 재작성 |
| **3.0** | **2026-01-14** | **Claim-Level Verification v3 (2026 SOTA) 구현** |

---

## 목차

1. [시작하기](#1-시작하기)
2. [프로젝트 구조](#2-프로젝트-구조)
3. [핵심 개념](#3-핵심-개념)
4. [에이전트 시스템](#4-에이전트-시스템)
5. [코드 컨벤션](#5-코드-컨벤션)
6. [새 기능 추가하기](#6-새-기능-추가하기)
7. [테스트](#7-테스트)

---

## 1. 시작하기

### 1.1 필수 도구

```bash
# Python 3.11+ 설치
# Docker Desktop 설치
# uv 패키지 매니저 설치
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 1.2 프로젝트 셋업

```bash
cd backend
uv sync

# 데이터베이스 시작
docker compose up -d db

# 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 설정

# DB 마이그레이션
uv run alembic upgrade head

# 서버 실행
uv run uvicorn app.main:app --reload --port 8000
```

### 1.3 확인

```bash
curl http://localhost:8000/health
# {"status":"healthy","service":"Livemap API"}

open http://localhost:8000/docs
```

---

## 2. 프로젝트 구조

```
backend/
├── app/
│   ├── main.py                    # FastAPI 진입점
│   │
│   ├── core/                      # 공유 인프라
│   │   ├── config.py              # 환경변수 (Settings)
│   │   ├── database.py            # SQLAlchemy 세션
│   │   └── lifespan.py            # 앱 시작/종료 (ClaimVerificationAgent 사용)
│   │
│   ├── agent/                     # 자율 에이전트 시스템
│   │   ├── graph/
│   │   │   └── state.py           # LangGraph 상태 정의
│   │   ├── tools/
│   │   │   ├── __init__.py        # ALL_TOOLS 익스포트
│   │   │   ├── search.py          # GDELT, Tavily, ddgs
│   │   │   ├── social.py          # Telegram, YouTube
│   │   │   └── media.py           # Video download
│   │   ├── triggers/
│   │   │   ├── base.py            # TriggerEvent 모델
│   │   │   ├── gdelt.py           # GDELT 트리거
│   │   │   ├── telegram.py        # Telegram 트리거
│   │   │   └── manager.py         # TriggerManager (LLM 분류)
│   │   ├── config.py              # 에이전트 설정
│   │   ├── scanner.py             # NewsScanner
│   │   ├── claim_extraction.py    # ★ V3: VeriScore 스타일 Claim 추출
│   │   ├── qa_verifier.py         # ★ V3: QA 기반 LLM 검증
│   │   ├── article_generator.py   # ★ V3: AP Style 기사 생성
│   │   ├── investigator_v3.py     # ★ V3: Claim-Level Verification (현재)
│   │   ├── investigator_v2.py     # V2: Deep Verification (레거시)
│   │   └── investigator.py        # V1: 기본 에이전트 (레거시)
│   │
│   ├── api/v1/
│   │   ├── routes/
│   │   │   ├── feeds.py           # Feed CRUD
│   │   │   └── agent.py           # Agent API
│   │   └── router.py              # 라우터 등록
│   │
│   ├── models/
│   │   └── feed.py                # Feed 모델
│   │
│   └── schemas/
│       ├── feed.py
│       └── agent.py
│
├── alembic/                       # DB 마이그레이션
├── docs/                          # 문서
└── pyproject.toml                 # 의존성
```

---

## 3. 핵심 개념

### 3.1 FastAPI 기본 패턴

**라우터 (엔드포인트 정의)**

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
    # 비즈니스 로직
    return {"status": "started"}
```

**의존성 주입**

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

### 3.2 Pydantic 스키마

```python
# app/schemas/agent.py
from pydantic import BaseModel, Field

class InvestigateRequest(BaseModel):
    topic: str = Field(..., min_length=5, description="조사할 주제")
    category: str = Field(default="general")

class InvestigateResponse(BaseModel):
    id: str
    status: str
    summary: str | None = None
```

### 3.3 SQLAlchemy 모델

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

### 3.4 비동기 프로그래밍

```python
# 병렬 실행 (권장)
results = await asyncio.gather(
    search_gdelt(query),
    search_duckduckgo(query),
    search_telegram(query),
)

# 순차 실행 (느림)
result1 = await search_gdelt(query)
result2 = await search_duckduckgo(query)
```

---

## 4. 에이전트 시스템

### 4.1 Claim-Level Verification Agent v3 (현재 사용)

```python
# app/agent/investigator_v3.py

class ClaimVerificationAgent:
    """
    2026 SOTA 기반 5단계 파이프라인 (AIC CTU + HerO 2 + VeriScore)

    Pipeline:
    1. EXTRACTOR: VeriScore 스타일 원자적 주장 추출
    2. RETRIEVER: 다중 소스 증거 수집 (GDELT/DDG/Tavily)
    3. VERIFIER: QA 기반 LLM 검증
    4. AGGREGATOR: Confidence-Weighted Voting
    5. SYNTHESIZER: AP Style 기사 생성
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

### 4.2 핵심 컴포넌트

```python
# app/agent/claim_extraction.py
class ClaimExtractor:
    """VeriScore 스타일 원자적 주장 추출"""
    async def extract(self, text: str) -> ClaimExtractionResult

# app/agent/qa_verifier.py
class QAVerifier:
    """QA 기반 LLM 검증 (AIC CTU 방식)"""
    async def verify_claim(self, claim, evidence_docs) -> ClaimVerdict
    async def verify_claims(self, claims, evidence_docs) -> VerificationResult

# app/agent/article_generator.py
class ArticleGenerator:
    """AP Style 기사 생성 (AP Stylebook 2024-2026 준수)"""
    async def generate(self, event_summary, verification_result) -> GeneratedArticle
```

### 4.3 AgentConfig

```python
# app/agent/config.py
class AgentSettings(BaseSettings):
    # LLM
    openai_api_key: str
    llm_model: str = "gpt-4o-mini"

    # Search
    tavily_api_key: str | None = None
    gdelt_enabled: bool = True

    # Scanner
    scan_interval_minutes: int = 15

    # Triggers
    significant_categories: list[str] = ["war", "protest", "terrorism", "military", "violence"]
```

### 4.3 도구 추가하기

**1단계: 도구 함수 정의**

```python
# app/agent/tools/search.py
from langchain_core.tools import tool

@tool
async def search_new_source(query: str, max_results: int = 10) -> list[dict]:
    """
    새로운 소스에서 검색합니다.

    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수

    Returns:
        검색 결과 리스트
    """
    # 구현
    results = await new_api.search(query, limit=max_results)
    return [{"title": r.title, "url": r.url, "content": r.content} for r in results]
```

**2단계: ALL_TOOLS에 등록**

```python
# app/agent/tools/__init__.py
from .search import search_new_source

ALL_TOOLS = [
    search_news_gdelt,
    search_web_free,
    search_new_source,  # 새 도구 추가
    search_telegram,
    search_youtube,
    search_web,
]
```

### 4.4 트리거 추가하기

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

## 5. 코드 컨벤션

### 5.1 네이밍

```python
# 함수: snake_case, 동사로 시작
async def search_news(query: str) -> list[dict]:
    pass

# 클래스: PascalCase
class DeepVerificationAgent:
    pass

# 상수: UPPER_SNAKE_CASE
MAX_RETRIES = 3
TOOL_TIMEOUT = 30.0
```

### 5.2 타입 힌트 (필수)

```python
from typing import Any

def process(
    text: str,
    threshold: float = 0.5,
    options: list[str] | None = None,
) -> dict[str, Any]:
    ...
```

### 5.3 에러 처리

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

### 5.4 로깅

```python
# 구조화된 로깅 권장
logger.info(
    "Research complete",
    extra={
        "subtopic_count": len(subtopics),
        "sources": len(sources),
        "execution_time": elapsed,
    },
)

# 피하기: print() 사용
# print(f"Research complete: {len(subtopics)} subtopics")  # ❌
```

---

## 6. 새 기능 추가하기

### 6.1 새 API 엔드포인트

**1단계: 스키마 정의**

```python
# app/schemas/example.py
from pydantic import BaseModel

class ExampleRequest(BaseModel):
    text: str

class ExampleResponse(BaseModel):
    result: str
```

**2단계: 라우터 생성**

```python
# app/api/v1/routes/example.py
from fastapi import APIRouter

router = APIRouter()

@router.post("", response_model=ExampleResponse)
async def process_example(request: ExampleRequest):
    return ExampleResponse(result="done")
```

**3단계: 라우터 등록**

```python
# app/api/v1/router.py
from app.api.v1.routes import example

api_router.include_router(
    example.router,
    prefix="/example",
    tags=["example"],
)
```

### 6.2 새 DB 테이블

**1단계: 모델 정의**

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

**2단계: 마이그레이션**

```bash
uv run alembic revision --autogenerate -m "Add example table"
uv run alembic upgrade head
```

---

## 7. 테스트

### 7.1 테스트 실행

```bash
# 전체 테스트
uv run pytest

# 특정 파일
uv run pytest tests/test_agent.py -v

# 특정 테스트
uv run pytest tests/test_agent.py::test_investigate -v
```

### 7.2 테스트 작성

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

## 부록: 유용한 명령어

```bash
# 서버 실행
uv run uvicorn app.main:app --reload --port 8000

# 마이그레이션
uv run alembic revision --autogenerate -m "설명"
uv run alembic upgrade head
uv run alembic downgrade -1

# 테스트
uv run pytest -v

# DB 접속
docker exec -it livemap-db psql -U livemap -d livemap
```

---

## 참고 자료

### 공식 문서

| 기술 | 문서 |
|------|------|
| FastAPI | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| Pydantic v2 | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| SQLAlchemy 2.0 | [docs.sqlalchemy.org](https://docs.sqlalchemy.org/) |
| LangGraph | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/) |
| tenacity | [tenacity.readthedocs.io](https://tenacity.readthedocs.io/) |

### 베스트 프랙티스

| 주제 | 링크 |
|------|------|
| FastAPI Best Practices | [github.com/zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) |
| LangGraph Production Template | [github.com/wassim249/fastapi-langgraph-agent-production-ready-template](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template) |

### 2026 SOTA 연구

| 연구 | 링크 |
|------|------|
| AIC CTU (FEVER 8 Winner) | [arxiv.org/html/2508.04390](https://arxiv.org/html/2508.04390) |
| HerO 2 (AVeriTeC 2025) | [arxiv.org/html/2507.11004](https://arxiv.org/html/2507.11004) |
| MedRAGChecker (2026) | [arxiv.org/html/2601.06519](https://arxiv.org/html/2601.06519) |
| Claim Verification Survey | [arxiv.org/html/2408.14317v2](https://arxiv.org/html/2408.14317v2) |
| VeriScore | [github.com/Yixiao-Song/VeriScore](https://github.com/Yixiao-Song/VeriScore) |
| AP Stylebook 2024-2026 | [Amazon](https://www.amazon.com/Associated-Press-Stylebook-2024-2026/dp/154160511X) |

---

*최종 업데이트: 2026-01-14*
*버전: 3.0 (Claim-Level Verification Agent v3)*
