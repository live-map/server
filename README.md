# Grapoll Backend

여론조사 플랫폼 Grapoll의 FastAPI 백엔드

## 기술 스택

| 항목 | 기술 |
|------|------|
| 프레임워크 | FastAPI 0.115+ |
| 언어 | Python 3.10+ |
| DB | PostgreSQL 16 (asyncpg + SQLAlchemy async) |
| 인증 | NextAuth.js JWE (A256CBC-HS512) |
| AI | LangGraph 리서치 파이프라인 (GPT-4o, Claude Sonnet) |
| 배포 | Fly.io Tokyo (nrt) |
| DB 호스팅 | Supabase Tokyo (PostgreSQL + pgvector) |
| CI/CD | GitHub Actions → flyctl deploy |

## 아키텍처

```
Controller (라우터) → Service (비즈니스 로직) → Repository (DB 쿼리)
```

의존성 주입(`Depends()`), async/await 일관 사용

## 프로젝트 구조

```
app/
├── api/v1/
│   ├── poll/          # 여론조사 (16개 엔드포인트)
│   │   ├── vote/      # 투표 서브모듈
│   │   └── comment/   # 댓글 서브모듈
│   ├── post/          # 커뮤니티 게시글 (11개 엔드포인트)
│   ├── comment/       # 커뮤니티 댓글
│   ├── media/         # S3 미디어 업로드
│   └── interpreter/   # JWT 인증 가드
├── core/              # config, database, lifespan, 예외
├── models/            # SQLAlchemy 모델 (14개 테이블)
├── services/          # S3, AI Research (LangGraph)
├── main.py            # 앱 진입점
fly.toml               # Fly.io 배포 설정
```

## 빠른 시작

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

필수 환경변수:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/postgres
AUTH_SECRET=nextauth-shared-secret
```

### 3. 개발 서버 실행

```bash
uv run uvicorn app.main:app --reload
```

### 4. Docker 실행

```bash
docker-compose up -d
```

## 주요 API 엔드포인트

| 모듈 | 주요 기능 |
|------|----------|
| `POST /api/v1/polls` | 여론조사 생성 |
| `POST /api/v1/polls/{id}/vote` | 투표 (6종 interaction type) |
| `POST /api/v1/polls/{id}/research` | AI 리서치 트리거 |
| `GET /api/v1/polls` | 목록 (popular/recent/ending_soon/closed) |
| `POST /api/v1/posts` | 게시글 작성 |
| `POST /api/v1/media/presigned-url` | S3 업로드 URL 생성 |
| `GET /health` | 헬스체크 |

전체 API 스펙은 `docs/project-context.md` 참조

## 배포

Fly.io Tokyo(nrt) + Supabase Tokyo(PostgreSQL)

```bash
# 배포
flyctl deploy

# 환경변수 설정
flyctl secrets set KEY=VALUE
```

GitHub Actions로 `dev` 브랜치 push 시 자동 배포

## 관련 문서

- `docs/project-context.md` - 전체 아키텍처 및 API 스펙
- `docs/deployment-strategy.md` - Fly.io + Supabase 마이그레이션 전략
- `docs/vote-integrity-research.md` - 1인 1투표 신뢰성 연구
