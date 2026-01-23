# Getting Started with LiveMap Backend

이 가이드는 약 5분 안에 로컬 개발을 위한 LiveMap 백엔드 설정을 도와드립니다.

## 사전 요구사항

- Python 3.11+
- PostgreSQL 15+ (pgvector 확장 포함)
- OpenAI API 키
- [uv](https://docs.astral.sh/uv/) 패키지 매니저

## 빠른 설정

### 1. 저장소 복제 및 의존성 설치

```bash
cd livemap/backend
uv sync
```

### 2. 환경 변수 설정

`.env` 파일 생성:

```bash
# 필수
OPENAI_API_KEY=sk-...

# 데이터베이스 (기본: PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/livemap

# 선택: 에이전트 설정
AGENT_GDELT_ENABLED=true
AGENT_REDDIT_ENABLED=true
AGENT_MIN_CONFIDENCE_SCORE=0.70
```

### 3. 서버 시작

```bash
uv run uvicorn app.main:app --reload
```

서버는 http://localhost:8000 에서 실행됩니다.

### 4. 설치 확인

```bash
# 헬스 체크
curl http://localhost:8000/health

# 스캔 트리거
curl -X POST http://localhost:8000/api/v1/agent/scan
```

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 애플리케이션 진입점
├── core/                # 설정, 데이터베이스, lifespan
├── api/v1/              # API 라우트 (agent, feeds)
├── agent/               # 뉴스 인텔리전스 에이전트
│   ├── scanner.py       # 다중 소스 스캐너
│   ├── event_verifier.py # Gate 0: 이벤트 검증
│   ├── confidence_scorer.py # 신뢰도 점수화
│   ├── cross_source_matcher.py # 소스 매칭
│   ├── triggers/        # 데이터 소스 커넥터
│   └── deduplication/   # 이벤트 중복 제거
├── models/              # SQLAlchemy ORM 모델
├── schemas/             # Pydantic 검증 스키마
└── services/            # 비즈니스 로직 레이어
```

## 핵심 개념

### 7단계 파이프라인

1. **Trigger 수집** - 여러 소스에서 이벤트 수집
2. **클러스터링** - 유사한 이벤트 그룹화
3. **소스 분류** - 티어 기반 소스 분류
4. **이벤트 검증 (Gate 0)** - 비이벤트 필터링
5. **신뢰도 점수화** - 다중 소스 신뢰도 계산
6. **콘텐츠 게이트** - 엔터테인먼트, 추측 필터링
7. **최종 출력** - 카테고리 제한, 포맷팅

### 소스 티어

| 티어 | 소스 | 신뢰도 |
|------|---------|-------------|
| Tier-1 | USGS, NOAA, GDELT | 0.90-0.99 |
| Tier-2 | Currents, WorldNews | 0.75-0.85 |
| Tier-3 | Reddit, Twitter | 0.30-0.40 |

### Two-Source Rule

이벤트는 게시 전 2개 이상의 독립 소스로부터 검증이 필요합니다 (예외: Tier-1 정부 소스).

## 테스트 실행

```bash
# 전체 테스트
uv run pytest tests/ -v

# 특정 테스트 파일
uv run pytest tests/unit/test_event_verifier.py -v

# 커버리지 포함
uv run pytest tests/ --cov=app --cov-report=html
```

## 일반적인 작업

### 수동 스캔 트리거

```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 조사 시작

```bash
curl -X POST http://localhost:8000/api/v1/agent/investigate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Iran attacks US bases in Iraq"}'
```

### 스캐너 상태 확인

```bash
curl http://localhost:8000/api/v1/agent/status
```

## 설정 참조

주요 환경 변수:

| 변수 | 기본값 | 설명 |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | LLM 기능에 필수 |
| `AGENT_GDELT_ENABLED` | true | GDELT 뉴스 소스 활성화 |
| `AGENT_REDDIT_ENABLED` | true | Reddit 소스 활성화 |
| `AGENT_MIN_CONFIDENCE_SCORE` | 0.70 | 게시 임계값 |
| `AGENT_EVENT_VERIFICATION_ENABLED` | true | Gate 0 활성화 |
| `AGENT_SCAN_INTERVAL_MINUTES` | 15 | 스캔 주기 |

전체 설정 옵션은 `app/agent/config.py`를 참조하세요.

## 문제 해결

### "Module not found" 오류
```bash
uv sync  # 의존성 재설치
```

### 데이터베이스 연결 오류
```bash
# PostgreSQL 실행 확인
pg_isready -h localhost -p 5432

# pgvector 확장 확인
psql -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 스캔에서 이벤트가 반환되지 않음
- `.env`에서 소스가 활성화되어 있는지 확인
- GDELT 접근 가능 여부 확인: `curl "https://api.gdeltproject.org/api/v2/doc/doc"`
- 테스트를 위해 `MIN_CONFIDENCE_SCORE` 낮추기

## 다음 단계

- [Concepts Overview](../concepts/README.md)에서 시스템 설계 읽기
- [API Reference](../api/README.md)에서 엔드포인트 탐색
- [Architecture Decisions](../adr/README.md)에서 설계 근거 확인
- [Trigger Guide](../guides/TRIGGER_GUIDE.md)에서 새 소스 추가 방법 검토
