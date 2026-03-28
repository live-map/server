# 인증 시스템 분석 (2026-03-28)

> 리팩토링 가이드: [`/docs/refactoring-guide.md`](/docs/refactoring-guide.md) 참조

## 종합 점수: 7.5/10

| 항목 | 점수 | 요약 |
|------|------|------|
| 아키텍처 설계 | 8/10 | 커스텀 OAuth + Stateless JWT, 계층 분리 우수 |
| 보안 | 6.5/10 | 기본 방어 OK, 토큰 무효화/rotation 부재 |
| 코드 품질 | 8.5/10 | 타입 안전, 관심사 분리, 주석 적절 |
| 유지보수성 | 7.5/10 | 구조 직관적, 미사용 코드/상수 중복 존재 |

---

## 아키텍처

**커스텀 OAuth 2.0 + Stateless JWT** (NextAuth.js 미사용)

```
[사용자] → [Google/Kakao] → [Next.js callback route] → [FastAPI OAuth] → [JWT 발급]
                                      ↓
                              httpOnly 쿠키에 저장
                                      ↓
                        매 요청마다 Authorization 헤더로 전송
```

- **Backend (FastAPI)**: OAuth 토큰 교환, JWT 발급/검증, 사용자 DB 관리
- **Frontend (Next.js)**: 쿠키 관리, UI, 라우트 보호

---

## DB 테이블

### `users` (활성)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | String(25) PK | CUID |
| name | String(255)? | 표시 이름 |
| email | String(255)? UNIQUE | 이메일 (계정 연동 키) |
| email_verified | DateTime? | 미사용 |
| hashed_password | String(255)? | 미사용 (OAuth 전용) |
| image | String(1000)? | 프로필 이미지 URL |
| role | Enum(USER, ADMIN) | 권한 |
| created_at / updated_at | DateTime | 타임스탬프 |

### `accounts` (활성)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | String(25) PK | CUID |
| user_id | FK→users.id CASCADE | 소유자 |
| type | String(255) | 항상 "oauth" |
| provider | String(255) | "google" / "kakao" |
| provider_account_id | String(255) | 제공자 측 사용자 ID |
| access_token / refresh_token | Text? | OAuth 제공자 토큰 (우리 JWT 아님) |
| expires_at | Integer? | Unix timestamp |
| token_type / scope / id_token / session_state | ? | OAuth 메타데이터 |
| **UK**: (provider, provider_account_id) | | |

### `sessions` — 미사용
JWT 전략이라 DB 세션 불필요. 호환성용으로 테이블만 존재.

### `verification_tokens` — 미사용
이메일 인증용. 현재 OAuth만 사용하므로 미사용.

---

## 토큰 시스템

| 토큰 | 알고리즘 | TTL | 저장 위치 |
|------|---------|-----|----------|
| Access Token | HS256 JWT | 30분 | httpOnly 쿠키 `grapoll-access-token` |
| Refresh Token | HS256 JWT | 30일 | httpOnly 쿠키 `grapoll-refresh-token` |

**JWT Payload**:
```json
{
  "sub": "cuid",
  "email": "...",
  "name": "...",
  "role": "USER",
  "type": "access",  // or "refresh"
  "iat": 1234567890,
  "exp": 1234569690
}
```

Access와 Refresh 모두 stateless JWT. DB 조회 없이 `JWT_SECRET`으로 서명/검증.

---

## OAuth 플로우

```
 1. OAuthButton → signInWithOAuth("google") (Server Action)
 2. → callbackUrl을 쿠키에 저장
 3. → GET /api/v1/auth/oauth/google/authorize?redirect_uri=...  (FastAPI)
 4. → FastAPI가 Google Authorization URL 생성 (+ CSRF state)
 5. → 브라우저가 Google 로그인 페이지로 이동
 6. → 사용자 동의
 7. → Google → GET /api/auth/callback/google?code=xxx&state=yyy  (Next.js)
 8. → Route handler → POST /api/v1/auth/oauth/google/callback  (FastAPI)
        - code → Google에서 access_token 교환
        - access_token → Google에서 userinfo 가져옴
        - DB에서 (provider, provider_account_id)로 기존 유저 검색
        - 없으면: email로 기존 유저 검색 (계정 연동) 또는 신규 생성
        - accounts 테이블에 OAuth 토큰 저장
        - 자체 JWT access_token + refresh_token 발급
 9. → Route handler가 httpOnly 쿠키 설정
10. → callbackUrl로 리다이렉트
```

---

## 인증 가드

| 가드 | 용도 | 실패 시 |
|------|------|---------|
| `CurrentUserOptional` | 로그인 선택 (투표 조회 등) | None 반환 |
| `CurrentUser` | 로그인 필수 (투표, 글쓰기 등) | 401 |
| `CurrentAdmin` | 관리자 전용 | 403 |

토큰 추출 순서: Authorization 헤더 → 쿠키

---

## Auto-Refresh

### Backend (TokenRefreshMiddleware) — Pure ASGI
1. `/auth/*`, `/health`, `/docs` 등 스킵
2. Access token 유효 → 통과
3. Access token 만료 + Refresh token 유효 → 새 access token 생성
   - Request Authorization 헤더 교체
   - Response에 `X-New-Access-Token` 헤더 추가
4. 둘 다 무효 → 통과 (downstream guard가 401)

### Frontend (tokens.ts)
- 모든 backend 응답에서 `x-new-access-token` 헤더 체크 → 쿠키 업데이트

---

## 클라이언트 인증 상태

**Server-side** (`lib/auth/session.ts`):
- `auth()` → `GET /api/v1/auth/me` → user 또는 null

**Client-side** (`lib/auth/auth-context.tsx`):
- `AuthProvider` → React 19 `use()` + singleton promise
- `useAuth()` → `{ user, status, refreshAuth, logout }`

**Route Protection** (`proxy.ts`):
- 쿠키 유무로 판단 (토큰 검증 없음)
- 보호 라우트: `/profile/**`, `/polls/*/edit`

---

## 로그아웃

```
Client: logout() → POST /api/auth/logout → POST /api/v1/auth/logout (no-op) → 쿠키 삭제
```

---

## 보안 평가

### 잘한 점
- httpOnly + sameSite:"lax" + Secure(prod) 쿠키
- OAuth state 파라미터 (CSRF 방어)
- CORS 제한 (프론트엔드 도메인만)
- Access/Refresh 분리 + 자동 갱신
- Backend가 OAuth secret 전담 (프론트엔드 노출 없음)

### 개선 필요 (우선순위순)

1. **Refresh Token Rotation** — 현재 refresh token 탈취 시 30일간 무제한 access token 발급 가능. 갱신 시 새 refresh token도 발급하고 기존 건 무효화해야 함.

2. **Token Blacklist** — 로그아웃/보안 사고 시 즉시 토큰 무효화 불가. Redis 기반 blacklist 필요. 현재 logout은 `pass` (no-op).

3. **OAuth State 검증** — state를 생성하지만 callback에서 실제 대조 로직 없음. CSRF 방어가 형식적.

4. **Route Protection 강화** — `proxy.ts`가 쿠키 유무만 체크. 만료/변조된 토큰으로도 보호 라우트 접근 허용 (서버에서 401 나오겠지만 UX 문제).

---

## 미사용 코드 정리 대상

| 항목 | 위치 | 상태 |
|------|------|------|
| `sessions` 테이블/모델 | `app/models/session.py` | 미사용 (JWT 전략) |
| `verification_tokens` 테이블/모델 | `app/models/verification_token.py` | 미사용 |
| `hashed_password` 컬럼 | `users` 테이블 | 미사용 (OAuth 전용) |
| `email_verified` 컬럼 | `users` 테이블 | 미사용 |
| Prisma 관련 docstring | `account.py`, `session.py` | 레거시 설명 |

---

## 파일 목록

### Backend
| 파일 | 역할 |
|------|------|
| `app/api/v1/auth/controller.py` | 5개 엔드포인트 |
| `app/api/v1/auth/service.py` | OAuth 인증 + 토큰 갱신 |
| `app/api/v1/auth/repository.py` | User/Account DB 접근 |
| `app/api/v1/auth/jwt.py` | JWT 생성/검증 |
| `app/api/v1/auth/jwt_guard.py` | CurrentUser/CurrentAdmin 가드 |
| `app/api/v1/auth/refresh_middleware.py` | ASGI 자동 갱신 미들웨어 |
| `app/api/v1/auth/lib/oauth.py` | Authlib OAuth 제공자 설정 |
| `app/api/v1/auth/dto/schemas.py` | Request/Response 모델 |
| `app/models/user.py` | User 모델 |
| `app/models/account.py` | Account 모델 |
| `app/models/session.py` | Session 모델 (미사용) |

### Frontend
| 파일 | 역할 |
|------|------|
| `lib/auth/tokens.ts` | 쿠키 읽기/쓰기, 헤더 빌드 |
| `lib/auth/session.ts` | 서버사이드 세션 체크 |
| `lib/auth/auth-context.tsx` | 클라이언트 AuthProvider + useAuth |
| `lib/auth/with-auth.ts` | Server Action 인증 래퍼 |
| `app/actions/auth.ts` | signInWithOAuth Server Action |
| `app/api/auth/callback/[provider]/route.ts` | OAuth 콜백 핸들러 |
| `app/api/auth/me/route.ts` | 현재 유저 조회 + 토큰 갱신 |
| `app/api/auth/logout/route.ts` | 로그아웃 |
| `app/auth/signin/page.tsx` | 로그인 페이지 |
| `components/auth/oauth-button.tsx` | OAuth 버튼 |
| `components/auth/login-modal.tsx` | 로그인 모달 |
| `proxy.ts` | 라우트 보호 |
