# How-To Guides

일반적인 개발 작업을 위한 실용적인 가이드입니다.

---

## 사용 가능한 가이드

### 설정 & 구성
- **[Configuration Reference](CONFIGURATION.md)** - 모든 환경 변수 및 설정

### 개발
- **[Trigger Guide](TRIGGER_GUIDE.md)** - 새 데이터 소스 추가
- **[Testing Guide](TESTING_GUIDE.md)** - 테스트 실행 및 작성

### 운영
- **[Deployment](DEPLOYMENT.md)** - 프로덕션 배포 옵션
- **[Troubleshooting](TROUBLESHOOTING.md)** - 일반적인 문제 및 해결책

---

## 빠른 시작 작업

### 서버 실행

```bash
# 개발 모드
uv run uvicorn app.main:app --reload --port 8000

# 프로덕션 모드
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 테스트 실행

```bash
# 전체 테스트
uv run pytest tests/ -v

# 특정 테스트 파일
uv run pytest tests/unit/test_event_verifier.py -v

# 커버리지 포함
uv run pytest tests/ --cov=app --cov-report=html
```

### 스캔 트리거

```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 상태 확인

```bash
curl http://localhost:8000/api/v1/agent/status
```

### 데이터베이스 마이그레이션

```bash
# 새 마이그레이션 생성
uv run alembic revision --autogenerate -m "Add new field"

# 마이그레이션 적용
uv run alembic upgrade head

# 한 단계 롤백
uv run alembic downgrade -1
```

---

## 일반적인 레시피

### 새 Trigger 소스 추가

1. `app/agent/triggers/`에 트리거 클래스 생성
2. `list[TriggerEvent]`를 반환하는 `scan()` 메서드 구현
3. `TriggerManager`에 등록
4. `config.py`에 설정 추가

자세한 내용은 [Trigger Guide](TRIGGER_GUIDE.md)를 참조하세요.

### 새 API 엔드포인트 추가

1. `app/schemas/`에 Pydantic 스키마 정의
2. `app/api/v1/routes/`에 라우트 생성
3. `app/api/v1/router.py`에 라우터 등록

### 이벤트 필터링 디버그

```bash
# Gate 0 거부 확인
docker compose logs api | grep "GATE0-REJECT"

# 신뢰도 점수화 확인
docker compose logs api | grep "CONFIDENCE"
```

---

## 관련 문서

- [Getting Started](../getting-started/README.md) - 초기 설정
- [Architecture](../architecture/README.md) - 시스템 설계
- [API Reference](../api/README.md) - 엔드포인트 문서
