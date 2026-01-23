# Installation Guide

이 가이드는 로컬 개발을 위한 LiveMap 백엔드 설정에 대한 상세 지침을 제공합니다.

---

## 사전 요구사항

### 필수 소프트웨어

| 소프트웨어 | 버전 | 용도 |
|----------|---------|---------|
| Python | 3.11+ | 런타임 |
| PostgreSQL | 15+ | 데이터베이스 |
| pgvector | 0.5+ | 벡터 유사도 |
| Docker | 24+ | 컨테이너 런타임 |
| uv | latest | 패키지 매니저 |

### API 키

| API | 필수 여부 | 용도 |
|-----|----------|---------|
| OpenAI | **예** | 검증용 LLM |
| Tavily | 선택 | 웹 검색 |
| Reddit | 선택 | 소셜 미디어 트리거 |

---

## Step 1: 사전 요구사항 설치

### macOS

```bash
# Homebrew가 없으면 설치
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.11 설치
brew install python@3.11

# PostgreSQL 설치
brew install postgresql@15
brew services start postgresql@15

# pgvector 설치
brew install pgvector

# Docker Desktop 설치
brew install --cask docker

# uv 패키지 매니저 설치
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

### Windows (WSL2 권장)

```powershell
# WSL2 설치
wsl --install

# 그 다음 WSL2 내에서 Ubuntu 지침 따르기
```

---

## Step 2: 데이터베이스 설정

### 옵션 A: Docker (권장)

```bash
cd backend

# pgvector가 포함된 PostgreSQL 시작
docker compose up -d db

# 확인
docker compose ps
# 예상: livemap-db가 포트 5432에서 실행 중
```

### 옵션 B: 로컬 PostgreSQL

```bash
# 데이터베이스 및 사용자 생성
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

## Step 3: 프로젝트 설정

### 저장소 복제 및 의존성 설치

```bash
cd livemap/backend

# Python 의존성 설치
uv sync

# 설치 확인
uv run python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
```

### 환경 설정

```bash
# 예제 환경 파일 복사
cp .env.example .env
```

`.env`를 설정에 맞게 편집:

```bash
# 필수
OPENAI_API_KEY=sk-...

# 데이터베이스 (Docker 기본값)
DATABASE_URL=postgresql+asyncpg://livemap:livemap@localhost:5432/livemap

# 선택: 검색 API
TAVILY_API_KEY=tvly-...

# 에이전트 설정
AGENT_GDELT_ENABLED=true
AGENT_REDDIT_ENABLED=true
AGENT_MIN_CONFIDENCE_SCORE=0.70
AGENT_EVENT_VERIFICATION_ENABLED=true
AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT=true
```

### 데이터베이스 마이그레이션

```bash
# Alembic 마이그레이션 실행
uv run alembic upgrade head

# 테이블 생성 확인
docker compose exec db psql -U livemap -d livemap -c "\dt"
```

---

## Step 4: 서버 시작

### 개발 모드

```bash
# 자동 리로드로 시작
uv run uvicorn app.main:app --reload --port 8000
```

### 프로덕션 모드

```bash
# 여러 워커로 시작
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Step 5: 설치 확인

### 헬스 체크

```bash
curl http://localhost:8000/health
# 예상: {"status":"healthy","service":"Livemap API"}
```

### API 문서

브라우저에서 열기: http://localhost:8000/docs

### 테스트 스캔

```bash
# 수동 스캔 트리거
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 일반적인 문제

### "Module not found" 오류

```bash
# 의존성 재설치
uv sync --force-reinstall
```

### 데이터베이스 연결 오류

```bash
# PostgreSQL 실행 확인
pg_isready -h localhost -p 5432

# Docker 사용 시
docker compose ps
docker compose logs db

# 데이터베이스 재시작
docker compose restart db
```

### pgvector 확장 누락

```bash
# Docker
docker compose exec db psql -U livemap -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 로컬 PostgreSQL
sudo -u postgres psql -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Zero-shot 모델 로딩 느림

첫 실행 시 BART-MNLI 모델(~1.6GB)을 다운로드합니다. 이후 실행에서는 캐시됩니다.

```bash
# 모델 미리 다운로드
uv run python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"
```

### OpenAI API 오류

```bash
# API 키 테스트
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## 선택: 개발 도구

### Pre-commit 훅

```bash
uv run pre-commit install
```

### IDE 설정 (VS Code)

확장 프로그램 설치:
- Python
- Pylance
- Ruff

`.vscode/settings.json`에 추가:
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "basic"
}
```

---

## 다음 단계

- [First Scan Tutorial](FIRST_SCAN.md) - 첫 번째 뉴스 스캔 실행
- [Project Structure](PROJECT_STRUCTURE.md) - 코드베이스 이해
- [Configuration Reference](../guides/CONFIGURATION.md) - 모든 설정

---

*더 많은 도움은 [Troubleshooting](../guides/TROUBLESHOOTING.md) 참조*
