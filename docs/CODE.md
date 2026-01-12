# Livemap Backend - 개발자 가이드

> 신입 개발자를 위한 코드베이스 완벽 가이드

---

## 목차

1. [시작하기](#1-시작하기)
2. [프로젝트 구조](#2-프로젝트-구조)
3. [핵심 개념](#3-핵심-개념)
4. [컴퓨터 공학 기초](#4-컴퓨터-공학-기초) ← **신규**
5. [코드 컨벤션](#5-코드-컨벤션)
6. [각 모듈 상세 설명](#6-각-모듈-상세-설명)
7. [새 기능 추가하기](#7-새-기능-추가하기)
8. [테스트](#8-테스트)
9. [자주 묻는 질문](#9-자주-묻는-질문)

---

## 1. 시작하기

### 1.1 필수 도구

```bash
# 1. Python 3.13+ 설치
# 2. Docker Desktop 설치
# 3. uv 패키지 매니저 설치
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 1.2 프로젝트 셋업

```bash
# 의존성 설치
cd backend
uv sync

# 데이터베이스 시작
docker compose up -d db searxng

# 환경변수 설정 (.env 파일 생성)
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://livemap:livemap123@localhost:5432/livemap
MISTRAL_API_KEY=your_key_here
DEBUG=true
EOF

# DB 마이그레이션
uv run alembic upgrade head

# 서버 실행
uv run uvicorn app.main:app --reload --port 8000
```

### 1.3 확인

```bash
# 헬스체크
curl http://localhost:8000/health

# API 문서
open http://localhost:8000/docs
```

---

## 2. 프로젝트 구조

```
backend/
├── app/                          # 메인 애플리케이션
│   ├── main.py                   # FastAPI 진입점
│   ├── config.py                 # 환경변수 설정
│   │
│   ├── api/                      # API 엔드포인트
│   │   └── v1/
│   │       ├── router.py         # 라우터 등록
│   │       ├── feeds.py          # GET /feeds
│   │       └── verify.py         # POST /verify
│   │
│   ├── db/                       # 데이터베이스
│   │   └── session.py            # SQLAlchemy 세션
│   │
│   ├── models/                   # SQLAlchemy 모델 (DB 테이블)
│   │   ├── feed.py               # feeds 테이블
│   │   └── channel.py            # channels 테이블
│   │
│   ├── schemas/                  # Pydantic 스키마 (요청/응답)
│   │   ├── feed.py
│   │   └── verify.py
│   │
│   └── services/                 # 비즈니스 로직
│       └── verification/         # 검증 파이프라인
│           ├── pipeline.py       # 메인 파이프라인
│           ├── stage0_preprocessing/  # Stage 0
│           ├── stage1/           # Stage 1
│           ├── stage2/           # Stage 2
│           ├── stage2_rag/       # Stage 2 RAG
│           └── stage3/           # Stage 3
│
├── alembic/                      # DB 마이그레이션
│   └── versions/                 # 마이그레이션 파일들
│
├── tests/                        # 테스트
└── docs/                         # 문서
```

---

## 3. 핵심 개념

### 3.1 4단계 검증 파이프라인

```
텍스트 입력
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Stage 0: 전처리                                  │
│ - 해시태그/멘션 정규화                           │
│ - 좌표 추출 (위도/경도)                          │
│ - 리포스트 감지                                  │
│ - 군사 용어 표준화                               │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Stage 1: 소스 신뢰도                             │
│ - 채널 신뢰도 점수 (40%)                         │
│ - 위치 추출 - spaCy NER (20%, 선택)              │
│ - 중복 감지 - BGE-M3 임베딩                      │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Stage 2: 증거 검증                               │
│ - SearXNG로 뉴스 검색                            │
│ - mDeBERTa NLI로 주장-증거 매칭                  │
│ - 소스 신뢰도 계층 (Tier 1-4)                    │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Stage 3: LLM 분석                                │
│ - Mistral Small                                  │
│ - 최종 판정 + 신뢰도 점수                        │
└─────────────────────────────────────────────────┘
    │
    ▼
검증 결과 (verified / partially_verified / unverified / false)
```

### 3.2 FastAPI 기본 패턴

**라우터 (엔드포인트 정의)**

```python
# app/api/v1/verify.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.verify import VerifyRequest, VerifyResponse

router = APIRouter()

@router.post("", response_model=VerifyResponse)
async def verify_content(
    request: VerifyRequest,              # Pydantic 스키마로 요청 검증
    db: AsyncSession = Depends(get_db),  # 의존성 주입으로 DB 세션
):
    """
    POST /api/v1/verify

    Docstring은 Swagger 문서에 표시됨
    """
    # 비즈니스 로직은 services에서 처리
    result = await run_pipeline(request.text)
    return VerifyResponse(...)
```

**의존성 주입 (Dependency Injection)**

```python
# app/db/session.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Depends(get_db)로 사용하면 자동으로:
    1. 세션 생성
    2. 함수에 주입
    3. 함수 종료 후 세션 정리
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### 3.3 Pydantic 스키마

**요청/응답 검증**

```python
# app/schemas/verify.py
from pydantic import BaseModel, ConfigDict, Field

class VerifyRequest(BaseModel):
    """POST /verify 요청 본문"""
    text: str = Field(
        ...,                          # 필수 필드
        min_length=10,                # 최소 길이
        max_length=5000,              # 최대 길이
        description="검증할 텍스트",
    )
    source_type: str = Field(
        default="API",
        description="소스 타입: TELEGRAM, X, RSS, API"
    )

class VerifyResponse(BaseModel):
    """POST /verify 응답"""
    status: str
    credibility_score: int = Field(ge=0, le=100)  # 0-100 범위

    # Pydantic v2 권장 방식 (ConfigDict 사용)
    model_config = ConfigDict(from_attributes=True)

    # 또는 기존 방식 (호환성)
    # class Config:
    #     from_attributes = True
```

### 3.4 SQLAlchemy 모델

**DB 테이블 정의**

```python
# app/models/feed.py
from sqlalchemy import String, Integer, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

class Feed(Base):
    """feeds 테이블 - 검증된 뉴스 저장"""

    __tablename__ = "feeds"

    # 컬럼 정의
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 외래키 관계
    channel_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("channels.id", ondelete="SET NULL"),
        nullable=True
    )
    channel = relationship("Channel", backref="feeds")

    # nullable 컬럼
    credibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

### 3.5 비동기 프로그래밍

```python
# ✅ 올바른 비동기 코드
async def verify_content(text: str):
    # 병렬 실행 (시간 절약)
    result1, result2, result3 = await asyncio.gather(
        check_duplicate(text),
        extract_locations(text),
        analyze_content(text),
    )

# ❌ 잘못된 코드 - 순차 실행 (느림)
async def verify_content_slow(text: str):
    result1 = await check_duplicate(text)    # 기다림
    result2 = await extract_locations(text)  # 기다림
    result3 = await analyze_content(text)    # 기다림
```

**CPU-bound 작업 처리**

```python
from fastapi.concurrency import run_in_threadpool

async def analyze_with_ml(text: str):
    # ML 추론은 CPU-bound → threadpool에서 실행
    result = await run_in_threadpool(ml_model.predict, text)
    return result
```

---

## 4. 컴퓨터 공학 기초

> FastAPI를 제대로 이해하려면 알아야 할 CS 지식

### 4.1 ASGI vs WSGI (왜 FastAPI가 빠른가?)

**WSGI (Web Server Gateway Interface)**
- Python 웹 표준 (PEP 3333, 2003년)
- **동기식**: 요청 1개 = 스레드 1개
- 요청 처리 중 다른 요청 대기
- 예: Flask, Django (기본 모드)

**ASGI (Asynchronous Server Gateway Interface)**
- 차세대 비동기 표준
- **비동기식**: 요청 N개 = 이벤트 루프 1개
- I/O 대기 중 다른 요청 처리 가능
- 예: FastAPI, Starlette

```
WSGI (동기):
요청1 ████████████████████████████
요청2          ████████████████████████████
요청3                   ████████████████████████████
      └─────────────────────────────────────────────→ 시간

ASGI (비동기):
요청1 ██░░░░██░░░░██  (░ = I/O 대기)
요청2   ██░░░░██░░░░██
요청3     ██░░░░██░░░░██
      └─────────────────→ 시간 (훨씬 짧음)
```

**Uvicorn이 빠른 이유**:
- **uvloop**: Python 기본 이벤트 루프보다 2~4배 빠름 (Cython 구현)
- **httptools**: 고성능 HTTP 파싱
- 메모리 효율: Gunicorn ~30MB vs Uvicorn ~20MB (워커당)

```python
# uvicorn 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 워커 수 공식: (2 × CPU 코어) + 1
# 4코어 머신 = 9 워커 권장
```

### 4.2 Python GIL (Global Interpreter Lock)

**GIL이란?**
- CPython의 전역 뮤텍스 (잠금 장치)
- **한 번에 하나의 스레드만** Python 코드 실행 가능
- 멀티코어 CPU에서도 진정한 병렬 실행 불가

```
GIL 있는 Python:
스레드1 ████░░░░████░░░░████  (████ = 실행, ░░░░ = 대기)
스레드2 ░░░░████░░░░████░░░░
        └── GIL 획득/해제 반복

진정한 병렬 (GIL 없음):
스레드1 ████████████████████
스레드2 ████████████████████
        └── 동시 실행
```

**그래서 왜 asyncio를 쓰는가?**

| 작업 유형 | GIL 영향 | 해결책 |
|----------|---------|--------|
| **I/O-bound** (네트워크, 파일, DB) | GIL 해제됨 | `asyncio` 또는 `threading` |
| **CPU-bound** (계산, ML 추론) | GIL 유지 | `multiprocessing` 또는 `run_in_threadpool` |

```python
# I/O-bound: asyncio (GIL 해제되므로 효율적)
async def fetch_data():
    response = await httpx.get(url)  # I/O 대기 중 GIL 해제
    return response

# CPU-bound: threadpool (GIL 경쟁하지만 블로킹 방지)
async def analyze_text(text: str):
    # ML 추론은 CPU-bound → threadpool에서 실행
    result = await run_in_threadpool(model.predict, text)
    return result

# CPU-bound 대량 작업: multiprocessing (GIL 우회)
from concurrent.futures import ProcessPoolExecutor

def heavy_computation(data):
    # 별도 프로세스 = 별도 GIL = 진정한 병렬
    return process(data)
```

**Python 3.13+ Free-Threaded Build**:
- GIL 제거된 실험적 빌드 존재
- `python3.13t` (t = threaded)
- 아직 프로덕션 권장 아님

### 4.3 의존성 주입 (Dependency Injection)

**왜 사용하는가?**

```python
# ❌ 나쁜 예: 강한 결합 (tight coupling)
class VerificationService:
    def __init__(self):
        self.db = PostgresDatabase()  # 하드코딩된 의존성
        self.cache = RedisCache()

    def verify(self, text: str):
        # 테스트할 때 실제 DB/Redis 필요...
        pass

# ✅ 좋은 예: 의존성 주입 (loose coupling)
class VerificationService:
    def __init__(self, db: Database, cache: Cache):
        self.db = db      # 주입받은 의존성
        self.cache = cache

    def verify(self, text: str):
        pass

# 테스트 시 모의 객체 주입 가능
service = VerificationService(db=MockDatabase(), cache=MockCache())
```

**FastAPI의 Depends()**:

```python
from fastapi import Depends

# 의존성 함수
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(token: str = Header()) -> User:
    return verify_token(token)

# 라우터에서 사용
@router.post("/verify")
async def verify(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db),           # DB 세션 주입
    user: User = Depends(get_current_user),       # 인증된 사용자 주입
):
    # db, user가 자동으로 주입됨
    pass
```

**DI의 장점**:

| 장점 | 설명 |
|------|------|
| **테스트 용이성** | 모의 객체로 쉽게 대체 |
| **유연성** | 구현체 변경 시 코드 수정 최소화 |
| **단일 책임** | 객체 생성과 사용 분리 |
| **재사용성** | 의존성 함수 여러 곳에서 공유 |

### 4.4 Connection Pooling (DB 연결 풀)

**왜 필요한가?**

```
❌ 연결 풀 없음:
요청1 → DB 연결 생성 (50ms) → 쿼리 → DB 연결 종료
요청2 → DB 연결 생성 (50ms) → 쿼리 → DB 연결 종료
요청3 → DB 연결 생성 (50ms) → 쿼리 → DB 연결 종료

✅ 연결 풀 사용:
[연결 풀: 연결1, 연결2, 연결3, ...]
요청1 → 풀에서 연결1 획득 (0.1ms) → 쿼리 → 연결1 반환
요청2 → 풀에서 연결2 획득 (0.1ms) → 쿼리 → 연결2 반환
요청3 → 풀에서 연결1 획득 (0.1ms) → 쿼리 → 연결1 반환
```

**SQLAlchemy 연결 풀 설정**:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=5,        # 기본 연결 수
    max_overflow=10,    # 추가 연결 허용 수 (총 15개까지)
    pool_timeout=30,    # 연결 대기 최대 시간 (초)
    pool_recycle=1800,  # 연결 재생성 주기 (초) - 30분
)
```

**연결 풀 크기 결정**:
```
권장: pool_size = (CPU 코어 수 × 2) + 동시 I/O 작업 수

예: 4코어, 동시 DB 쿼리 5개 예상
   pool_size = (4 × 2) + 5 = 13
```

### 4.5 N+1 문제 (ORM의 함정)

**문제 상황**:

```python
# 채널 100개 조회
channels = await session.execute(select(Channel))

for channel in channels:
    # 각 채널마다 feeds 조회 → 100번의 추가 쿼리!
    print(channel.feeds)  # Lazy Loading 발동

# 총 쿼리 수: 1 (채널) + 100 (피드) = 101개 ← N+1 문제!
```

**해결책: Eager Loading**

```python
from sqlalchemy.orm import joinedload, selectinload

# 방법 1: joinedload (JOIN 사용)
# 한 번의 쿼리로 모든 데이터 가져옴
query = select(Channel).options(joinedload(Channel.feeds))

# 생성되는 SQL:
# SELECT * FROM channels JOIN feeds ON channels.id = feeds.channel_id

# 방법 2: selectinload (IN 절 사용)
# 2번의 쿼리 (1: 채널, 2: 모든 피드)
query = select(Channel).options(selectinload(Channel.feeds))

# 생성되는 SQL:
# SELECT * FROM channels
# SELECT * FROM feeds WHERE channel_id IN (1, 2, 3, ...)
```

**언제 무엇을 쓰는가?**

| 관계 | 권장 방식 | 이유 |
|------|----------|------|
| **1:1, N:1** (many-to-one) | `joinedload` | 중복 행 없음 |
| **1:N** (one-to-many) | `selectinload` | 중복 행 방지 |
| **M:N** (many-to-many) | `selectinload` | 카테시안 곱 방지 |

```python
# 실제 사용 예
from sqlalchemy.orm import selectinload

async def get_channels_with_feeds(session: AsyncSession):
    query = (
        select(Channel)
        .options(selectinload(Channel.feeds))  # 1:N 관계
        .where(Channel.is_active == True)
    )
    result = await session.execute(query)
    return result.scalars().all()

# 총 쿼리: 2개 (N+1 → 2로 감소!)
```

### 4.6 HTTP 기본 원리

**HTTP 메서드와 멱등성**:

| 메서드 | 용도 | 멱등성 | Request Body |
|--------|------|--------|--------------|
| `GET` | 조회 | ✅ Yes | ❌ No |
| `POST` | 생성 | ❌ No | ✅ Yes |
| `PUT` | 전체 수정 | ✅ Yes | ✅ Yes |
| `PATCH` | 부분 수정 | ❌ No | ✅ Yes |
| `DELETE` | 삭제 | ✅ Yes | ❌ No |

**멱등성 (Idempotency)**: 같은 요청을 여러 번 해도 결과가 동일

```python
# ✅ 멱등: PUT /users/1 {"name": "Kim"}
# 몇 번을 호출해도 user 1의 이름은 "Kim"

# ❌ 비멱등: POST /users {"name": "Kim"}
# 호출할 때마다 새 사용자 생성
```

**HTTP 상태 코드**:

| 범위 | 의미 | 예시 |
|------|------|------|
| `2xx` | 성공 | 200 OK, 201 Created, 204 No Content |
| `3xx` | 리다이렉션 | 301 Moved, 304 Not Modified |
| `4xx` | 클라이언트 오류 | 400 Bad Request, 401 Unauthorized, 404 Not Found |
| `5xx` | 서버 오류 | 500 Internal Error, 503 Service Unavailable |

```python
from fastapi import HTTPException, status

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_feed(request: FeedCreate):
    if not request.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text is required"
        )
    # ...
    return {"id": new_feed.id}

@router.get("/{feed_id}")
async def get_feed(feed_id: int):
    feed = await get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feed {feed_id} not found"
        )
    return feed
```

**REST 설계 원칙**:

```
✅ 좋은 REST API:
GET    /feeds          # 목록 조회
GET    /feeds/123      # 단일 조회
POST   /feeds          # 생성
PUT    /feeds/123      # 전체 수정
PATCH  /feeds/123      # 부분 수정
DELETE /feeds/123      # 삭제

❌ 나쁜 API:
GET    /getFeeds
POST   /createFeed
POST   /feeds/delete/123
```

---

## 5. 코드 컨벤션

### 5.1 파일 구조

```python
# 파일 맨 위: 모듈 설명
"""
Stage 1 Pipeline: Local NLP verification.

V1 (Legacy - news articles):
- spaCy NER for location extraction (REQUIRED)

V2 (Social media optimized):
- spaCy NER for location extraction (OPTIONAL)
"""

# 임포트 순서: 표준 라이브러리 → 서드파티 → 로컬
import asyncio
from dataclasses import dataclass

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.verification.stage1 import run_stage1_async
```

### 5.2 네이밍 컨벤션

```python
# 함수: snake_case, 동사로 시작
def calculate_score(text: str) -> float:
    pass

async def run_pipeline(text: str):
    pass

# 클래스: PascalCase
class VerificationResult:
    pass

# 상수: UPPER_SNAKE_CASE
MAX_TEXT_LENGTH = 5000
SIMILARITY_THRESHOLD = 0.85

# private 함수/변수: _로 시작
def _internal_helper():
    pass
```

### 5.3 타입 힌트 (필수!)

```python
# ✅ 항상 타입 힌트 사용
def process_text(
    text: str,
    threshold: float = 0.5,
    options: list[str] | None = None,
) -> dict[str, float]:
    ...

# Dataclass로 복잡한 반환값 정의
@dataclass
class Stage1Result:
    locations: list[dict]
    has_location: bool
    score: float
    should_continue: bool

async def run_stage1(text: str) -> Stage1Result:
    ...
```

### 5.4 에러 처리

```python
from fastapi import HTTPException

async def verify(text: str):
    # 입력 검증
    if len(text) < 10:
        raise HTTPException(
            status_code=400,
            detail="Text must be at least 10 characters"
        )

    try:
        result = await external_api_call()
    except ExternalAPIError as e:
        # 외부 API 에러는 로깅하고 계속 진행
        logger.error(f"External API failed: {e}")
        result = None
```

### 5.5 로깅

```python
import logging

logger = logging.getLogger(__name__)

def process(text: str):
    logger.info(f"Processing text: {text[:50]}...")
    logger.debug(f"Full text: {text}")  # 디버그에서만

    try:
        result = heavy_computation()
    except Exception as e:
        logger.exception("Computation failed")  # 스택 트레이스 포함
        raise
```

---

## 6. 각 모듈 상세 설명

### 6.1 Stage 0: 전처리

```
app/services/verification/stage0_preprocessing/
├── __init__.py          # 모듈 export
├── pipeline.py          # 전처리 오케스트레이션
├── normalizer.py        # 텍스트 정규화
├── coordinate_extractor.py  # 좌표 추출
├── repost_detector.py   # 리포스트 감지
└── terminology.py       # 군사 용어 사전
```

**사용 예시:**

```python
from app.services.verification.stage0_preprocessing import run_stage0

result = run_stage0(
    text="Forwarded from @channel\n#Ukraine HIMARS at 48.5, 37.9",
    platform="TELEGRAM"
)

print(result.normalized_text)      # 정규화된 텍스트
print(result.has_coordinates)      # True
print(result.is_repost)           # True
print(result.hashtags)            # ['Ukraine']
print(result.has_military_content) # True (HIMARS 감지)
```

**코드 분석 - normalizer.py:**

```python
# 해시태그 추출 정규식
HASHTAG_PATTERN = re.compile(r"#(\w+)", re.UNICODE)

def normalize_text(text: str) -> NormalizationResult:
    # 1. 해시태그 추출 후 # 제거
    hashtags = HASHTAG_PATTERN.findall(text)      # ['Ukraine']
    normalized = HASHTAG_PATTERN.sub(r"\1", text) # #Ukraine → Ukraine

    # 2. 멘션 제거
    normalized = MENTION_PATTERN.sub("", normalized)

    # 3. URL을 [URL]로 대체
    normalized = URL_PATTERN.sub("[URL]", normalized)

    return NormalizationResult(
        normalized_text=normalized,
        extracted_hashtags=hashtags,
        ...
    )
```

### 6.2 Stage 1: 소스 신뢰도

```
app/services/verification/stage1/
├── __init__.py
├── pipeline.py           # 오케스트레이션 (V1 + V2)
├── channel_credibility.py  # 채널 신뢰도 계산
├── spacy_ner.py          # 위치 추출
├── duplicate.py          # 중복 감지
├── fake_news.py          # (V2에서 비활성화)
└── subjectivity.py       # (V2에서 비활성화)
```

**채널 신뢰도 계산:**

```python
# app/services/verification/stage1/channel_credibility.py

def calculate_channel_credibility(
    subscriber_count: int | None,
    channel_age_days: int | None,
    is_verified: bool,
    historical_accuracy: float | None,
) -> ChannelCredibilityResult:
    score = 0.0

    # 구독자 수 (0-0.25)
    if subscriber_count >= 100000:
        score += 0.25
    elif subscriber_count >= 10000:
        score += 0.20
    elif subscriber_count >= 1000:
        score += 0.10

    # 채널 나이 (0-0.25)
    if channel_age_days >= 730:  # 2년+
        score += 0.25
    elif channel_age_days >= 365:  # 1년+
        score += 0.15

    # 인증 상태 (0-0.2)
    if is_verified:
        score += 0.2

    # 과거 정확도 (0-0.3)
    if historical_accuracy:
        score += historical_accuracy * 0.3
    else:
        score += 0.15  # 미지 = 중립

    # Tier 계산: 1(최고) ~ 5(미지)
    tier = 5 if score < 0.2 else 4 if score < 0.4 else 3 if score < 0.6 else 2 if score < 0.8 else 1

    return ChannelCredibilityResult(score=score, tier=tier)
```

**Stage 1 V2 점수 계산:**

```python
def calculate_stage1_score_v2(
    channel_score: float,     # 채널 신뢰도
    has_location: bool,       # NER 위치 발견
    is_duplicate: bool,       # 중복 여부
    has_coordinates: bool,    # Stage 0 좌표 발견
) -> float:
    if is_duplicate:
        return 0.0  # 중복은 무조건 차단

    score = 0.0
    score += channel_score * 0.4      # 채널: 40%
    score += 0.4                       # 비중복 기본: 40%
    score += 0.2 if has_location else 0.0  # 위치: 20% (선택)
    score += 0.1 if has_coordinates else 0.0  # 좌표 보너스: 10%

    return min(score, 1.0)
```

### 6.3 Stage 2: 증거 검증

```
app/services/verification/stage2_rag/
├── __init__.py
├── pipeline.py           # RAG 파이프라인
├── evidence_retriever.py # SearXNG 검색
├── evidence_checker.py   # NLI 매칭
├── models.py            # 데이터 모델
├── telegram_searcher.py # (미구현) 텔레그램 검색
└── osint_searcher.py    # (미구현) OSINT 검색
```

**NLI (Natural Language Inference) 이해:**

```python
# NLI는 전제(premise)와 가설(hypothesis)의 관계를 판단

# 예시:
premise = "러시아 미사일이 키이우를 공격했다"
hypothesis = "우크라이나 수도가 공격받았다"
# → ENTAILMENT (전제가 가설을 지지)

premise = "전투가 계속되고 있다"
hypothesis = "휴전이 선언되었다"
# → CONTRADICTION (모순)

premise = "군인들이 이동 중이다"
hypothesis = "전투가 시작될 것이다"
# → NEUTRAL (판단 불가)
```

**증거 검색 흐름:**

```python
# app/services/verification/stage2_rag/pipeline.py

class RAGVerificationPipeline:
    async def verify(self, claim: str) -> RAGVerificationResult:
        # 1. 검색 쿼리 생성
        queries = [claim, f"fact check {claim}"]

        # 2. SearXNG로 뉴스 검색
        evidences = await self.retriever.search(queries)

        # 3. 각 증거에 NLI 적용
        for evidence in evidences:
            nli_result = self.checker.check(claim, evidence.text)
            # nli_result.verdict = "SUPPORTS" | "REFUTES" | "NEUTRAL"

        # 4. 집계
        supporting = [r for r in results if r.verdict == "SUPPORTS"]
        refuting = [r for r in results if r.verdict == "REFUTES"]

        # 5. 최종 판정
        if len(supporting) >= 2 and len(supporting) > len(refuting):
            verdict = "SUPPORTED"
        elif len(refuting) >= 2:
            verdict = "REFUTED"
        else:
            verdict = "UNCERTAIN"
```

### 6.4 Stage 3: LLM 분석

```
app/services/verification/stage3/
├── __init__.py
├── pipeline.py    # 오케스트레이션
└── mistral.py     # Mistral API 호출
```

**Mistral API 호출:**

```python
# app/services/verification/stage3/mistral.py

SYSTEM_PROMPT = """You are a fact-checking assistant.
Analyze the claim and provide a verdict."""

async def analyze_claim(
    claim: str,
    context: str | None,  # Stage 1+2 결과
) -> Stage3Result:
    response = await mistral_client.chat(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Claim: {claim}\nContext: {context}"}
        ],
        response_format={"type": "json_object"},  # JSON 응답 강제
    )

    # JSON 파싱
    result = json.loads(response.content)
    return Stage3Result(
        verdict=Verdict(result["verdict"]),
        confidence=result["confidence"],
        reasoning=result["reasoning"],
    )
```

---

## 7. 새 기능 추가하기

### 7.1 새 API 엔드포인트 추가

**1단계: 스키마 정의**

```python
# app/schemas/example.py
from pydantic import BaseModel, Field

class ExampleRequest(BaseModel):
    text: str = Field(..., min_length=1)

class ExampleResponse(BaseModel):
    result: str
    score: float
```

**2단계: 라우터 생성**

```python
# app/api/v1/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.example import ExampleRequest, ExampleResponse

router = APIRouter()

@router.post("", response_model=ExampleResponse)
async def process_example(
    request: ExampleRequest,
    db: AsyncSession = Depends(get_db),
):
    # 비즈니스 로직
    return ExampleResponse(result="done", score=0.95)
```

**3단계: 라우터 등록**

```python
# app/api/v1/router.py
from app.api.v1 import example

api_router.include_router(
    example.router,
    prefix="/example",
    tags=["example"],
)
```

### 7.2 새 DB 테이블 추가

**1단계: 모델 정의**

```python
# app/models/example.py
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

class Example(Base):
    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

**2단계: 모델 등록**

```python
# app/models/__init__.py
from app.models.example import Example

__all__ = ["Feed", "Channel", "Example"]
```

**3단계: 마이그레이션 생성**

```bash
uv run alembic revision --autogenerate -m "Add example table"
uv run alembic upgrade head
```

### 7.3 새 Stage 컴포넌트 추가

```python
# app/services/verification/stage1/new_analyzer.py
from dataclasses import dataclass

@dataclass
class NewAnalyzerResult:
    score: float
    details: dict

def analyze(text: str) -> NewAnalyzerResult:
    # 분석 로직
    return NewAnalyzerResult(score=0.8, details={})

# pipeline.py에서 임포트하여 사용
```

---

## 8. 테스트

### 8.1 테스트 실행

```bash
# 전체 테스트
uv run pytest

# 특정 파일
uv run pytest tests/test_pipeline_v2.py -v

# 특정 테스트
uv run pytest tests/test_pipeline_v2.py::TestStage0Preprocessing -v
```

### 8.2 테스트 작성

```python
# tests/test_example.py
import pytest
from app.services.example import process

class TestExample:
    def test_basic_case(self):
        result = process("test input")
        assert result.score > 0.5

    def test_edge_case(self):
        result = process("")
        assert result.score == 0.0

# 비동기 테스트
@pytest.mark.asyncio
async def test_async_function():
    result = await async_process("test")
    assert result is not None
```

---

## 9. 자주 묻는 질문

### Q: 왜 location이 없어도 통과하나요?

V2에서는 소셜 미디어 최적화를 위해 location을 **선택 사항**으로 변경했습니다.

```python
# V1 (기존): 위치 없음 → SKIP
if not has_location:
    return SKIPPED

# V2 (신규): 위치 없음 → 점수만 감소, 계속 진행
score += 0.2 if has_location else 0.0  # 20% 보너스
```

### Q: 모델 로딩이 느려요

첫 요청 시 ML 모델을 로드합니다 (30-60초). 이후 요청은 빠릅니다.

```python
# app/main.py - lifespan에서 미리 로드
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 모델 로드
    load_all_models()
    yield
```

### Q: DB 세션은 어떻게 관리하나요?

`Depends(get_db)`를 사용하면 자동으로 관리됩니다.

```python
@router.post("")
async def endpoint(db: AsyncSession = Depends(get_db)):
    # 함수 내에서 db 사용
    # 함수 종료 시 자동 정리
```

### Q: 새 환경변수를 추가하려면?

```python
# app/config.py
class Settings(BaseSettings):
    # 기존 설정...

    # 새 설정 추가
    NEW_SETTING: str = "default_value"
    NEW_NUMBER: int = 100

# 사용
from app.config import settings
print(settings.NEW_SETTING)
```

---

## 부록: 유용한 명령어

```bash
# 서버 실행 (개발)
uv run uvicorn app.main:app --reload --port 8000

# 마이그레이션 생성
uv run alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
uv run alembic upgrade head

# 마이그레이션 롤백
uv run alembic downgrade -1

# 테스트 실행
uv run pytest -v

# DB 접속
docker exec -it livemap-db psql -U livemap -d livemap

# 로그 확인
docker compose logs -f
```

---

## 참고 자료

### 공식 문서

| 기술 | 문서 |
|------|------|
| FastAPI | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| Pydantic v2 | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| SQLAlchemy 2.0 | [docs.sqlalchemy.org](https://docs.sqlalchemy.org/) |
| Alembic | [alembic.sqlalchemy.org](https://alembic.sqlalchemy.org/) |
| uv | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |

### 베스트 프랙티스 가이드

| 주제 | 링크 |
|------|------|
| FastAPI Best Practices | [github.com/zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) |
| FastAPI + SQLAlchemy 2.0 + Pydantic v2 | [medium.com/@tclaitken](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308) |
| Production Boilerplate | [github.com/grillazz/fastapi-sqlalchemy-asyncpg](https://github.com/grillazz/fastapi-sqlalchemy-asyncpg) |

### CS 기초 심화 학습

| 주제 | 링크 |
|------|------|
| ASGI vs WSGI 비교 | [deployhq.com - Python Application Servers 2025](https://www.deployhq.com/blog/python-application-servers-in-2025-from-wsgi-to-modern-asgi-solutions) |
| Python GIL 이해 | [codecademy.com - Understanding GIL](https://www.codecademy.com/article/understanding-the-global-interpreter-lock-gil-in-python) |
| asyncio vs threading | [superfastpython.com - ThreadPoolExecutor vs AsyncIO](https://superfastpython.com/threadpoolexecutor-vs-asyncio/) |
| SQLAlchemy N+1 문제 | [hevalhazalkurt.com - Defeat N+1 Problem](https://hevalhazalkurt.com/blog/how-to-defeat-the-n1-problem-with-joinedload-selectinload-and-subqueryload/) |
| SQLAlchemy Loading Strategies | [medium.com/@dresraceran](https://medium.com/@dresraceran/understanding-sqlalchemys-eager-loading-joinedload-selectinload-and-contains-eager-e12d98c8c8b0) |
| Uvicorn 성능 분석 | [leapcell.io - Uvicorn Performance](https://leapcell.io/blog/uvicorn-performance-python-asgi) |

### 주요 변경사항 (2025-2026)

**Pydantic v2 (FastAPI 0.100+)**:
- `orm_mode = True` → `from_attributes = True`
- `class Config` → `model_config = ConfigDict(...)`
- 성능 대폭 향상 (Rust 기반 파싱)

**SQLAlchemy 2.0**:
- `postgresql://` → `postgresql+asyncpg://` (비동기)
- `Mapped[T]` + `mapped_column()` 권장
- `select()` 문법 변경

---

*최종 수정: 2026-01-12*
