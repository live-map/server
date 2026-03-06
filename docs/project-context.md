# Grapoll - 프로젝트 컨텍스트

> 여론조사 플랫폼 Grapoll의 전체 아키텍처 및 API 스펙 문서

---

## 1. 프로젝트 개요

**프로젝트명**: Grapoll (여론조사 플랫폼)
**구성**: 모노레포 (`/livemap/backend` + `/livemap/client`)

| 항목 | 백엔드 | 프론트엔드 |
|------|--------|-----------|
| 프레임워크 | FastAPI 0.115+ | Next.js 16 (App Router) |
| 언어 | Python 3.10+ | TypeScript 5 (strict) |
| DB | PostgreSQL 16 (asyncpg) | PostgreSQL (NextAuth 세션용) |
| 인증 | NextAuth JWE 디코딩 | NextAuth v5 (Google/Kakao OAuth) |
| 배포 | Railway | Vercel |
| 브랜치 | dev (메인) | - |

---

## 2. 백엔드 아키텍처

### 2.1 계층 구조

```
Controller (라우터) → Service (비즈니스 로직) → Repository (DB 쿼리)
```

- 의존성 주입: `Depends()`로 DB 세션, 인증, 서비스 주입
- 비동기: async/await 일관 사용 (asyncpg + SQLAlchemy async)

### 2.2 디렉토리 구조

```
app/
├── api/v1/
│   ├── poll/          # 여론조사 (Controller→Service→Repository)
│   │   ├── vote/      # 투표 서브모듈
│   │   └── comment/   # 댓글 서브모듈
│   ├── post/          # 커뮤니티 게시글 (동일 패턴)
│   ├── comment/       # 커뮤니티 댓글
│   ├── media/         # S3 미디어 업로드
│   └── interpreter/   # JWT 인증 가드
├── core/              # config, database, lifespan, 예외
├── models/            # SQLAlchemy 모델 (14개 테이블)
├── services/          # S3, AI Research
└── main.py            # 앱 진입점, 미들웨어, 라우터 등록
```

### 2.3 데이터베이스 스키마 (14개 테이블)

**인증 (NextAuth 동기화)**:

| 테이블 | 주요 컬럼 | 비고 |
|--------|----------|------|
| users | id(CUID), name, email, role(USER/ADMIN), image | 핵심 유저 |
| accounts | provider, provider_account_id, access_token | OAuth 계정 |
| sessions | session_token, expires | DB 세션 |
| verification_tokens | identifier, token, expires | 이메일 인증 |

**여론조사**:

| 테이블 | 주요 컬럼 | 비고 |
|--------|----------|------|
| polls | title, description, type(OFFICIAL/SUGGESTED), status(DRAFT/ACTIVE/CLOSED), interaction_type(6종), total_votes, view_count, ai_content, ai_metrics(JSON) | 핵심 |
| poll_options | text, order, vote_count | 선택지 |
| votes | user_id, poll_id, option_id, slider_value, selected_option_ids(JSON), ranking_data(JSON) | UniqueConstraint(user_id, poll_id) |
| poll_sources | title, url, source_type(NEWS/PAPER/ARTICLE/VIDEO/OTHER) | AI 출처 |
| poll_comments | content, parent_id(self-join), option_id, depth, likes | 대댓글 지원 |
| poll_comment_likes | comment_id, user_id | UniqueConstraint |

**커뮤니티**:

| 테이블 | 주요 컬럼 | 비고 |
|--------|----------|------|
| posts | title, content, like_count, view_count, comment_count, popularity_score | Reddit-style 점수 |
| comments | content, parent_id(self-join), depth, order_number | 무한 대댓글 |
| post_media | media_type(IMAGE/VIDEO), url, thumbnail_url, file_size, duration | S3 업로드 |
| post_likes | post_id, user_id | UniqueConstraint |

### 2.4 인증 시스템

- NextAuth.js JWE 토큰 (A256CBC-HS512)
- Cookie 또는 Authorization 헤더에서 추출
- 3단계 가드: `CurrentUserOptional` / `CurrentUser` / `CurrentAdmin`
- Cookie 이름: `authjs.session-token` (dev) / `__Secure-authjs.session-token` (prod)

### 2.5 API 엔드포인트 전체 목록

#### Poll 모듈 (16개)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | /polls | Optional | 여론조사 생성 (비로그인시 demo_hackathon_user) |
| GET | /polls | None | 목록 (sort: popular/recent/ending_soon/closed) |
| GET | /polls/{id} | None | 상세 (옵션, 출처, 댓글 포함) |
| PATCH | /polls/{id} | Required(작성자) | 수정 |
| DELETE | /polls/{id} | Required(작성자) | 소프트 삭제 |
| POST | /polls/{id}/vote | Optional | 투표 (6종 interaction_type, 비로그인시 anon-{uuid4}) |
| GET | /polls/{id}/vote | Required | 내 투표 조회 |
| POST | /polls/{id}/comments | Required | 댓글 작성 |
| GET | /polls/{id}/comments | None | 댓글 목록 (트리) |
| DELETE | /polls/{id}/comments/{cid} | Required(작성자) | 댓글 삭제 |
| POST | /polls/{id}/comments/{cid}/like | Required | 댓글 좋아요 토글 |
| GET | /polls/hot-debate | None | 핫 디베이트 (접전 poll) |
| GET | /polls/suggested | None | 유저 제안 목록 |
| POST | /polls/{id}/view | Optional | 조회수 증가 |
| POST | /polls/{id}/research | Admin | AI 리서치 트리거 |
| GET | /polls/{id}/research/status | None | 리서치 상태 |

#### Post 모듈 (11개)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | /posts | Required | 게시글 작성 (미디어 포함) |
| GET | /posts | Optional | 목록 (7종 sort) |
| GET | /posts/{id} | Optional | 상세 (조회수 증가) |
| PATCH | /posts/{id} | Required(작성자) | 수정 |
| DELETE | /posts/{id} | Required(작성자) | 소프트 삭제 |
| DELETE | /posts/{id}/hard | Admin | 하드 삭제 |
| POST | /posts/{id}/like | Required | 좋아요 |
| DELETE | /posts/{id}/like | Required | 좋아요 취소 |
| GET | /posts/{id}/likes | None | 좋아요 목록 |
| POST | /posts/{id}/media | Required(작성자) | 미디어 추가 |
| DELETE | /posts/{id}/media/{mid} | Required(작성자) | 미디어 삭제 |

#### Comment 모듈 (~7개)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | /comments | Required | 댓글/대댓글 작성 |
| GET | /comments | None | 플랫 목록 |
| GET | /comments/tree | None | 트리 목록 |
| GET | /comments/{id} | None | 상세 |
| PATCH | /comments/{id} | Required(작성자) | 수정 |
| DELETE | /comments/{id} | Required(작성자) | 소프트 삭제 |
| GET | /comments/{id}/replies | None | 대댓글 목록 |

#### Media 모듈 (2개)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | /media/config | None | 업로드 설정 |
| POST | /media/presigned-url | Required | S3 presigned URL 생성 |

#### 기타

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | /health | 헬스체크 |

### 2.6 투표 상호작용 타입 (6종)

| 타입 | 요청 필드 | 설명 |
|------|----------|------|
| BINARY | optionId | A vs B 선택 |
| SINGLE_CHOICE | optionId | 단일 선택 |
| MULTIPLE_CHOICE | selectedOptionIds[] | 다중 선택 |
| SLIDER | sliderValue (0-100) | 스케일 |
| EMOJI_REACTION | optionId | 이모지 반응 |
| RANKING | rankingData[] | 순위 투표 |

### 2.7 AI 리서치 시스템 (LangGraph)

```
perspective_discovery → planner → [web_search | academic_search | fact_check] (병렬)
→ gap_analyzer → outline_generator → synthesizer → reviewer (최대 2회 재시도)
```

**역할별 모델 자동 선택**:
- Planner: GPT-4o-mini
- Synthesizer: GPT-4o (또는 Claude Sonnet)
- Reviewer: GPT-4o (크로스 모델 검증)

**외부 API**: Tavily(웹검색) → DuckDuckGo(fallback), Semantic Scholar(학술), Google Fact Check, Jina Reader(본문추출), Unsplash(썸네일)

**결과 저장**: `polls.ai_content`(마크다운), `polls.ai_metrics`(JSON), `poll_sources`(자동생성)

### 2.8 외부 서비스

| 서비스 | 용도 | 필수여부 |
|--------|------|---------|
| AWS S3 + CloudFront | 미디어 업로드/CDN | 선택 |
| OpenAI / Anthropic | LLM (리서치) | 선택 |
| Tavily / DuckDuckGo | 웹 검색 | DuckDuckGo만 필수(무료) |
| Semantic Scholar | 학술 논문 | 선택 |
| Google Fact Check | 팩트체크 | 선택 |
| Unsplash | 썸네일 이미지 | 선택 |

### 2.9 미들웨어/보안

- CORS: FRONTEND_URL + localhost (DEBUG)
- Rate Limiting: 60req/min per IP (slowapi)
- X-Request-ID: 모든 요청에 UUID 추가
- 예외 핸들러: 422(검증), 429(Rate Limit), 500(서버)

---

## 3. 프론트엔드 아키텍처

### 3.1 기술 스택

- Next.js 16 (App Router, React 19, React Compiler)
- NextAuth v5 (JWT 세션, Google/Kakao OAuth)
- Tailwind CSS v4 + shadcn/ui (Radix UI)
- React Hook Form + Zod v4
- OpenAPI-TS (hey-api, 백엔드 스펙 자동 생성)
- Sentry (에러 모니터링)

### 3.2 페이지 구조

```
/ (홈)                        → 인기 poll 목록, Hot Debate, 유저 제안
/polls/all                    → 전체 poll 목록
/polls/[pollId]               → poll 상세 + 투표 + AI 콘텐츠 + 댓글
/polls/[pollId]/edit          → poll 수정 (인증 필요)
/polls/suggest/new            → poll 생성 (인증 필요)
/community                    → 게시글 목록 (7종 정렬)
/community/new                → 게시글 작성 (인증 필요)
/community/[postId]           → 게시글 상세 + 댓글
/profile                      → 프로필
/profile/edit                 → 프로필 수정
/profile/settings/*           → 설정 (이메일, 비밀번호, 소셜)
/auth/signin                  → 로그인
```

### 3.3 API 호출 패턴

```
클라이언트 컴포넌트 → Server Action → apiFetch(JWT 토큰 추가) → 백엔드 fetch
```

- Poll API: 수동 `apiFetch()` 래핑
- Post/Comment/Media API: OpenAPI-TS 자동 생성 클라이언트
- 캐싱: Next.js Data Cache + revalidateTag (ISR, 30-60초)

### 3.4 인증 흐름

```
OAuth 버튼 → signInWithOAuth() → NextAuth → Google/Kakao
→ JWT 생성 (id, role) → 쿠키 저장 → 백엔드에 Bearer 토큰 전달
```

- 커스텀 PostgreSQL 어댑터 (users, accounts 직접 관리)
- Proxy 미들웨어: /profile/*, /polls/*/edit → 인증 필요

### 3.5 상태 관리

- 글로벌: SessionProvider, ThemeProvider, LoginModalProvider, Toaster
- 로컬: useState, React Hook Form
- 데이터: Server Actions + Next.js Cache Tags

---

## 4. 프론트-백 연동 스펙

### 4.1 DTO 변환 규칙

- 백엔드: snake_case (Python)
- 프론트: camelCase (TypeScript)
- 변환: Pydantic alias (`populate_by_name=True`)

### 4.2 인증 토큰 공유

- 동일한 AUTH_SECRET으로 JWE 토큰 암/복호화
- 백엔드: `fastapi-nextauth-jwt`로 디코딩
- 프론트: NextAuth v5가 생성

### 4.3 에러 코드 매핑

| 백엔드 | 프론트 메시지 |
|--------|-------------|
| 401 | "로그인이 필요합니다" |
| 403 | "권한이 없습니다" |
| 404 | "존재하지 않는 ..." |
| 409 | "이미 투표하셨습니다" / "이미 좋아요" |
| 503 | "서비스를 이용할 수 없습니다" |

---

## 5. 배포 환경

| 항목 | 현재 | 비고 |
|------|------|------|
| 백엔드 | Railway | 비용 효율 연구 후 변경 예정 |
| 프론트엔드 | Vercel | .vercel/ 설정 존재 |
| DB | PostgreSQL 16 | Railway 또는 외부 |
| CI/CD | GitHub Actions (OCI SSH, 레거시) | Railway 자동 배포로 전환 중 |

---

## 6. 검증 필요 사항

### 코드 품질
- [ ] tests/ 디렉토리 50+ 파일 레거시 → 정리 또는 재작성 필요
- [ ] CI/CD yml이 OCI 기준 → Railway 전환 시 업데이트 필요
- [ ] Dockerfile에 Railway PORT 환경변수 하드코딩
- [ ] git status에 미추적 스크린샷 파일 다수 (.png)

### API 일관성
- [ ] Poll API: 수동 apiFetch 래핑 / Post API: OpenAPI-TS 자동생성 → 패턴 불일치
- [ ] Poll 생성 시 비로그인 → demo_hackathon_user 자동 할당 (의도적)
- [ ] 투표 시 비로그인 → anon-{uuid4} 사용 (Poll 생성과 별도 처리)
- [ ] Vote의 user_id에 FK 없음 (anonymous voting 지원)

### 기능 완성도
- [ ] EMOJI_REACTION 타입 프론트 구현 상태 확인
- [ ] 프로필 수정/설정 페이지 백엔드 API 없음 (프론트만 있음?)
- [ ] 비밀번호 변경 - hashed_password 컬럼은 있으나 관련 API 없음
