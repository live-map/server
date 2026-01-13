# Livemap Backend

실시간 글로벌 분쟁/뉴스 지도 서비스를 위한 자율 에이전트 기반 백엔드

## 아키텍처

### 자율 에이전트 시스템 (NEW)

LangGraph + ReAct 패턴 기반 자율 검증 시스템:

1. **다중 소스 트리거** - GDELT, Twitter, Telegram에서 실시간 이벤트 감지
2. **자율 수집** - 에이전트가 관련 정보를 자동으로 수집/검증
3. **LLM 분석** - GPT-4o-mini로 신뢰도 분석 및 기사화

### 기존 검증 파이프라인 (Legacy)

간소화된 2단계 파이프라인:
- Stage 1: 로컬 NLP (위치 추출, 중복 감지)
- Stage 3: LLM 분석 (Mistral)

## 빠른 시작

### 1. 의존성 설치

```bash
cd backend
uv sync
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

필수 설정:
```env
# Database
DATABASE_URL=postgresql+asyncpg://livemap:livemap123@localhost:5432/livemap

# Autonomous Agent (권장)
AGENT_OPENAI_API_KEY=your_openai_api_key
AGENT_TAVILY_API_KEY=your_tavily_api_key
```

### 3. Docker로 실행

```bash
docker-compose up -d
```

### 4. API 서버 실행 (개발)

```bash
uv run uvicorn app.main:app --reload
```

## API 엔드포인트

### 자율 에이전트

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /api/v1/agent/investigate` | 주제에 대한 자율 조사 시작 |
| `GET /api/v1/agent/status/{id}` | 조사 상태 확인 |
| `POST /api/v1/agent/scan` | 다중 소스 트리거 스캔 |

### 검증 파이프라인 (Legacy)

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /api/v1/verify` | 텍스트 검증 |
| `POST /api/v1/verify/detailed` | 상세 검증 결과 |

### 피드

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/v1/feeds` | 피드 목록 |
| `GET /api/v1/feeds/publishable` | 발행 가능 피드 |
| `GET /api/v1/feeds/{id}` | 피드 상세 |

## 트리거 소스

### GDELT (뉴스)
- 100,000+ 글로벌 뉴스 소스
- 무료, API 키 불필요

### Twitter/X (Twikit)
- 실시간 소셜 미디어 모니터링
- 개인 계정 필요 (ToS 주의)

### Telegram (Telethon)
- OSINT 채널 모니터링
- API 인증 필요

## 개발

```bash
# 테스트 실행
uv run pytest

# 타입 체크
uv run mypy app

# 린트
uv run ruff check app
```
