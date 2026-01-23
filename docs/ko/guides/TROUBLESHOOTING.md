# Troubleshooting Guide

LiveMap의 일반적인 문제와 해결책입니다.

---

## 빠른 진단

```bash
# 서버 헬스 체크
curl http://localhost:8000/health

# 에이전트 상태 확인
curl http://localhost:8000/api/v1/agent/status

# 최근 로그 보기
docker compose logs --tail=100 api
```

---

## 설치 문제

### "Module not found" 오류

**증상**: 서버 시작 시 임포트 오류

**해결책**:
```bash
# 모든 의존성 재설치
uv sync --force-reinstall

# 특정 패키지 누락 시
uv add <package-name>
```

### Python 버전 불일치

**증상**: 구문 오류 또는 임포트 실패

**해결책**:
```bash
# Python 버전 확인
python --version  # 3.11+ 이어야 함

# 특정 Python 버전 사용
uv python pin 3.11
uv sync
```

---

## 데이터베이스 문제

### 연결 거부

**증상**: `psycopg.OperationalError: connection refused`

**해결책**:
```bash
# PostgreSQL 실행 확인
pg_isready -h localhost -p 5432

# Docker 사용 시
docker compose ps
docker compose up -d db

# 연결 문자열 확인
echo $DATABASE_URL
```

### pgvector 확장 누락

**증상**: `extension "vector" does not exist`

**해결책**:
```bash
# Docker
docker compose exec db psql -U livemap -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 로컬 PostgreSQL
sudo apt install postgresql-15-pgvector
sudo -u postgres psql -d livemap -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 마이그레이션 오류

**증상**: Alembic 마이그레이션 실패

**해결책**:
```bash
# 현재 마이그레이션 상태 확인
uv run alembic current

# 특정 버전으로 리셋
uv run alembic downgrade -1
uv run alembic upgrade head

# 완전히 깨진 경우 리셋 (주의: 데이터 손실)
uv run alembic stamp head
```

---

## API 문제

### OpenAI API 오류

**증상**: `openai.AuthenticationError` 또는 속도 제한

**해결책**:
```bash
# API 키 테스트
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 속도 제한 확인 (.env에서)
AGENT_MAX_CONCURRENT_LLM_CALLS=3
AGENT_LLM_TIMEOUT_SECONDS=60
```

### 429 Too Many Requests (GDELT)

**증상**: GDELT 트리거가 속도 제한 오류 반환

**해결책**:
```bash
# 스캔 간격 증가
AGENT_SCAN_INTERVAL_MINUTES=30  # 15 대신

# 또는 GDELT 호출 사이에 지연 추가
AGENT_GDELT_DELAY_SECONDS=5
```

---

## 스캐너 문제

### 이벤트 수집 안 됨

**증상**: 스캐너 실행되지만 0개 이벤트 반환

**체크리스트**:
```bash
# 1. 소스 활성화 확인
echo $AGENT_GDELT_ENABLED  # true여야 함

# 2. GDELT API 직접 확인
curl "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&maxrecords=10"

# 3. 오류 로그 확인
docker compose logs api | grep -i "error\|exception"
```

### 이벤트 필터링되지만 기사 생성 안 됨

**증상**: 이벤트가 필터를 통과했지만 DB에 기사 없음

**체크리스트**:
```bash
# 1. 중복 확인
# 로그에서 "SKIPPING: Duplicate event" 찾기

# 2. 조사 제한 확인
echo $AGENT_MAX_INVESTIGATIONS  # 기본값 3

# 3. LLM 타임아웃 확인
echo $AGENT_LLM_TIMEOUT_SECONDS  # 기본값 60
```

### Gate 0에서 너무 많은 이벤트 거부

**증상**: 이벤트 검증에서 높은 거부율

**진단**:
```bash
# 거부 이유 로그 확인
docker compose logs api | grep "GATE0-REJECT"

# 일반적인 패턴:
# [GATE0-REJECT] NOT_EVENT: pattern 'movie' matched
# [GATE0-REJECT] ZERO_SHOT: sports (0.92)
```

**해결책**:
- `event_verifier.py`에서 패턴 매칭 조정
- Zero-shot 신뢰도 임계값 낮추기
- 키워드가 너무 넓은지 확인

---

## 성능 문제

### 임베딩 생성 느림

**증상**: 클러스터링에 10초 이상 소요

**해결책**:
```bash
# 1. 모델 미리 다운로드
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# 2. 배치 크기 줄이기
AGENT_EMBEDDING_BATCH_SIZE=32

# 3. GPU 사용 (가능한 경우)
CUDA_VISIBLE_DEVICES=0 uv run uvicorn app.main:app --reload
```

### Zero-shot 모델 로딩 느림

**증상**: 첫 요청에 30초 이상 소요

**해결책**:
```bash
# BART-MNLI 모델 미리 다운로드
uv run python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"

# 모델은 ~/.cache/huggingface/에 캐시됨
```

### 메모리 문제

**증상**: OOM 오류 또는 느린 성능

**해결책**:
```bash
# 1. 임베딩 배치 크기 제한
AGENT_MAX_EVENTS_PER_SCAN=100

# 2. 동시 LLM 호출 줄이기
AGENT_MAX_CONCURRENT_LLM_CALLS=2

# 3. 스왑 추가 (제한된 RAM인 경우)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Docker 문제

### 컨테이너 시작 안 됨

**증상**: 컨테이너가 즉시 종료

**진단**:
```bash
# 종료 이유 확인
docker compose logs api

# 일반적인 원인:
# - 환경 변수 누락
# - 포트가 이미 사용 중
# - 데이터베이스 준비 안 됨
```

### 컨테이너 간 네트워크 문제

**증상**: API가 데이터베이스에 접근할 수 없음

**해결책**:
```bash
# 네트워크 확인
docker network ls
docker network inspect livemap_default

# 서비스가 같은 네트워크에 있는지 확인
docker compose down
docker compose up -d
```

---

## 일반적인 오류 메시지

| 오류 | 원인 | 해결책 |
|-------|-------|----------|
| `OPENAI_API_KEY not set` | API 키 누락 | .env 파일에 추가 |
| `Connection refused: 5432` | DB 미실행 | PostgreSQL 시작 |
| `extension "vector" does not exist` | pgvector 누락 | 확장 설치 |
| `Too many requests (429)` | 속도 제한 | 스캔 빈도 줄이기 |
| `Timeout waiting for response` | LLM 느림/과부하 | 타임아웃 증가 |
| `No module named 'xxx'` | 의존성 누락 | `uv sync` 실행 |

---

## 도움 받기

### 디버그 정보 수집

```bash
# 디버그 리포트 생성
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

### 이슈 리포팅

이슈 리포팅 시 포함할 내용:
1. 오류 메시지 (전체 트레이스백)
2. 재현 단계
3. 환경 상세 (OS, Python 버전)
4. 설정 (API 키 제외)
5. 최근 로그

---

## 관련 문서

- [Installation](../getting-started/INSTALLATION.md) - 설정 가이드
- [Configuration](CONFIGURATION.md) - 모든 설정
- [Architecture](../architecture/README.md) - 시스템 설계
