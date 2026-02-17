# OAuth Authentication Implementation - Backend (FastAPI)

이 문서는 OAuth 2.0 Authorization Code Flow가 백엔드에서 어떻게 구현되었는지 설명합니다.

아래 다이어그램의 각 단계(Phase)가 백엔드 코드의 어느 부분에서 처리되는지 매핑합니다.

```
사용자          서비스 Client         Authorization Server       Resource Server
  │                │                        │                        │
  │  1. 서비스 접근  │                        │                        │
  │───────────────>│                        │                        │
  │  2. Client ID, │                        │                        │
  │  Redirect_URI  │                        │                        │
  │<───────────────│                        │                        │
  │                │  3. 로그인 페이지 요청    │                        │
  │                │  Client ID, Redirect URI│                        │
  │────────────────────────────────────────>│                        │
  │                │  4. 로그인 페이지 제공    │                        │
  │<────────────────────────────────────────│                        │
  │  5. ID/PW 입력  │                        │                        │
  │────────────────────────────────────────>│                        │
  │  6. Authorization code 발급              │                        │
  │<────────────────────────────────────────│                        │
  │  7. Redirect_URI로                      │                        │
  │  Authorization code 전달                 │                        │
  │───────────────>│                        │                        │
  │                │  8. Authorization code로 │                        │
  │                │  Access Token 요청       │                        │
  │                │───────────────────────>│                        │
  │                │  9. Access Token 발급    │                        │
  │                │<───────────────────────│                        │
  │ 10. 인증 완료   │                        │                        │
  │<───────────────│                        │                        │
  │ 11. 서비스 요청  │                        │                        │
  │───────────────>│                        │                        │
  │                │  12. Access Token으로    │                        │
  │                │  API 호출               │                        │
  │                │────────────────────────────────────────────────>│
  │                │  13. 검증 및 서비스 제공   │                        │
  │                │<────────────────────────────────────────────────│
  │ 14. 서비스 제공  │                        │                        │
  │<───────────────│                        │                        │
```

---

## Phase 2: Client ID, Redirect_URI 전달

**사용자가 로그인 버튼을 클릭하면, 서비스 Client가 OAuth Provider의 인증 URL을 생성합니다.**

### 엔드포인트

```
GET /api/v1/auth/oauth/{provider}/authorize?redirect_uri=...
```

### 구현 위치

**Controller**: `app/api/v1/auth/controller.py`

```python
@router.get("/oauth/{provider}/authorize")
async def get_oauth_authorize_url(
    provider: str,
    redirect_uri: str = Query(...),
):
    state = secrets.token_urlsafe(32)
    url = get_authorization_url(provider, redirect_uri, state)
    return AuthUrlResponse(url=url, state=state)
```

**OAuth Service**: `app/services/auth/oauth.py`

```python
def get_authorization_url(provider: str, redirect_uri: str, state: str) -> str:
    config = get_provider_config(provider)
    client = create_oauth_client(provider, redirect_uri)
    url, _ = client.create_authorization_url(
        config["authorize_url"],
        state=state,
    )
    return url
```

Authlib의 `AsyncOAuth2Client`가 `client_id`, `redirect_uri`, `scope`, `state`를 포함한 인증 URL을 생성합니다.

### Provider 설정

`app/services/auth/oauth.py`에서 각 Provider의 엔드포인트를 관리합니다:

```python
OAUTH_PROVIDERS = {
    "google": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "kakao": {
        "client_id": settings.KAKAO_CLIENT_ID,
        "client_secret": settings.KAKAO_CLIENT_SECRET,
        "authorize_url": "https://kauth.kakao.com/oauth/authorize",
        "token_url": "https://kauth.kakao.com/oauth/token",
        "userinfo_url": "https://kapi.kakao.com/v2/user/me",
        "scope": "profile_nickname profile_image account_email",
    },
}
```

---

## Phase 3-6: 로그인 페이지 요청 → Authorization Code 발급

**이 단계들은 OAuth Provider(Google, Kakao)가 직접 처리합니다.**

사용자가 Provider의 로그인 페이지에서 ID/PW를 입력하면, Provider가 Authorization Code를 생성하여 `redirect_uri`로 리다이렉트합니다.

백엔드는 이 과정에 관여하지 않습니다.

---

## Phase 7-9: Authorization Code → Access Token 교환

**사용자가 Authorization Code와 함께 redirect_uri로 돌아오면, 백엔드가 이 Code를 Access Token으로 교환합니다.**

### 엔드포인트

```
POST /api/v1/auth/oauth/{provider}/callback
```

### Request Body

```json
{
  "code": "authorization_code_from_provider",
  "state": "csrf_state_string",
  "redirect_uri": "https://frontend.com/api/auth/callback/google"
}
```

### 구현 위치

**Controller**: `app/api/v1/auth/controller.py`

```python
@router.post("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await authenticate_oauth(db, provider, body.code, body.redirect_uri)
    return AuthResponse(**result)
```

**Auth Service**: `app/services/auth/service.py`

```python
async def authenticate_oauth(db, provider, code, redirect_uri):
    # Phase 8: Authorization Code로 Access Token 요청
    oauth_tokens = await exchange_code_for_token(provider, code, redirect_uri)

    # Phase 9에 해당: Provider가 Access Token 발급
    # oauth_tokens에 access_token, refresh_token 등이 포함됨
```

**OAuth Service**: `app/services/auth/oauth.py`

```python
async def exchange_code_for_token(provider, code, redirect_uri):
    config = get_provider_config(provider)
    client = create_oauth_client(provider, redirect_uri)
    token = await client.fetch_token(config["token_url"], code=code)
    return dict(token)
```

Authlib가 `fetch_token()`을 통해 Authorization Code를 Provider의 Token Endpoint에 전송하고, Access Token을 받아옵니다.

---

## Resource Server에서 사용자 정보 조회

**Access Token을 사용하여 Provider의 Resource Server(userinfo endpoint)에서 사용자 프로필을 조회합니다.**

이 단계는 다이어그램의 Phase 12-13에 해당하지만, 인증 과정에서 한 번 실행됩니다.

### 구현 위치

**OAuth Service**: `app/services/auth/oauth.py`

```python
async def fetch_user_profile(provider: str, access_token: str) -> dict:
    config = get_provider_config(provider)

    async with AsyncOAuth2Client(
        token={"access_token": access_token, "token_type": "Bearer"}
    ) as client:
        resp = await client.get(config["userinfo_url"])
        data = resp.json()

    # Provider별 응답 정규화
    if provider == "google":
        return {
            "provider_account_id": data["sub"],
            "email": data.get("email"),
            "name": data.get("name"),
            "image": data.get("picture"),
        }
    elif provider == "kakao":
        account = data.get("kakao_account", {})
        profile = account.get("profile", {})
        return {
            "provider_account_id": str(data["id"]),
            "email": account.get("email"),
            "name": profile.get("nickname"),
            "image": profile.get("profile_image_url"),
        }
```

---

## 사용자 생성/조회 및 계정 연동

**Provider로부터 받은 프로필 정보로 데이터베이스에서 사용자를 찾거나 새로 생성합니다.**

### 구현 위치

**Auth Service**: `app/services/auth/service.py`

```python
async def get_or_create_user(db, provider, profile, oauth_tokens):
    # 1. OAuth 계정으로 기존 사용자 검색
    user = SELECT u.* FROM users u
           JOIN accounts a ON u.id = a.user_id
           WHERE a.provider = ? AND a.provider_account_id = ?

    if user:
        # 기존 사용자 → OAuth 토큰 업데이트
        return user

    # 2. 이메일로 기존 사용자 검색 (계정 연동)
    if profile.email:
        user = SELECT * FROM users WHERE email = ?

    # 3. 새 사용자 생성
    if not user:
        user = User(id=cuid(), name=..., email=..., role="USER")
        db.add(user)

    # 4. OAuth 계정 연동
    account = Account(
        id=cuid(),
        user_id=user.id,
        provider=provider,
        provider_account_id=profile["provider_account_id"],
        access_token=oauth_tokens["access_token"],
        ...
    )
    db.add(account)
    db.commit()
```

---

## Phase 10: 자체 JWT 토큰 발급

**사용자 인증이 완료되면, 백엔드가 자체 JWT(Access Token + Refresh Token)를 발급합니다.**

### 구현 위치

**JWT Service**: `app/services/auth/jwt.py`

```python
def create_access_token(user_id, email, name, role):
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=30),  # 30분
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id):
    token = secrets.token_urlsafe(64)  # 랜덤 문자열
    expires_at = now + timedelta(days=30)  # 30일
    return token, expires_at
```

**Auth Service**: `app/services/auth/service.py`

```python
# JWT 토큰 발급
access_token = create_access_token(user.id, user.email, user.name, user.role)
refresh_token, expires = create_refresh_token(user.id)

# Refresh Token 해시를 sessions 테이블에 저장
session = SessionModel(
    id=cuid(),
    session_token=sha256(refresh_token),
    user_id=user.id,
    expires=expires,
)
db.add(session)
```

### Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "random_opaque_string...",
  "token_type": "Bearer",
  "user": {
    "id": "clx7a9b2c...",
    "email": "user@example.com",
    "name": "홍길동",
    "image": "https://...",
    "role": "USER"
  }
}
```

---

## Phase 11-14: 인증된 요청 처리

**사용자가 서비스를 이용할 때, JWT Access Token으로 인증합니다.**

### JWT Guard (인증 인터셉터)

**위치**: `app/api/v1/interpreter/jwt_guard.py`

```python
async def get_current_user(request, token_from_header):
    # 1. Authorization 헤더 또는 쿠키에서 토큰 추출
    token = token_from_header or await get_token_from_cookie(request)

    # 2. JWT 디코딩 및 검증
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])

    # 3. JWTPayload 객체로 변환
    return JWTPayload(
        user_id=payload["sub"],
        email=payload["email"],
        role=payload["role"],
        ...
    )
```

### Controller에서 사용

```python
@router.post("/polls")
async def create_poll(
    data: PollCreate,
    current_user: CurrentUser,  # JWT Guard가 주입
    service: PollServiceDep,
):
    poll = await service.create_poll(user_id=current_user.user_id, ...)
```

### 인증 가드 종류

| Guard | 용도 | 실패 시 |
| --- | --- | --- |
| `CurrentUser` | 인증 필수 | 401 Unauthorized |
| `CurrentUserOptional` | 인증 선택 | `None` 반환 |
| `CurrentAdmin` | 관리자 전용 | 403 Forbidden |

---

## Token Refresh

**Access Token이 만료되면 Refresh Token으로 새 Access Token을 발급받습니다.**

### 엔드포인트

```
POST /api/v1/auth/refresh
```

### 구현 위치

**Auth Service**: `app/services/auth/service.py`

```python
async def refresh_access_token(db, refresh_token):
    # 1. Refresh Token 해시로 sessions 테이블 검색
    token_hash = sha256(refresh_token)
    session = SELECT * FROM sessions WHERE session_token = token_hash

    # 2. 만료 확인
    if session.expires < now:
        raise ValueError("Refresh token expired")

    # 3. 사용자 조회
    user = SELECT * FROM users WHERE id = session.user_id

    # 4. 새 Access Token 발급
    return create_access_token(user.id, user.email, user.name, user.role)
```

---

## Logout

```
POST /api/v1/auth/logout
```

Refresh Token을 sessions 테이블에서 삭제합니다. Access Token은 만료될 때까지 유효하지만 (30분), Refresh Token이 폐기되므로 갱신이 불가능합니다.

---

## 파일 구조

```
server/app/
├── api/v1/
│   ├── auth/
│   │   ├── __init__.py
│   │   └── controller.py        # Auth 엔드포인트 (authorize, callback, refresh, logout, me)
│   └── interpreter/
│       ├── __init__.py
│       └── jwt_guard.py         # JWT 검증 가드 (CurrentUser, CurrentAdmin)
├── services/auth/
│   ├── __init__.py
│   ├── oauth.py                 # Authlib OAuth 클라이언트 (URL 생성, 코드 교환, 프로필 조회)
│   ├── jwt.py                   # JWT 토큰 생성/검증 (PyJWT)
│   └── service.py               # 인증 비즈니스 로직 (사용자 생성, 토큰 발급, 갱신)
├── models/
│   ├── user.py                  # User 모델
│   ├── account.py               # Account 모델 (OAuth 계정 연동)
│   └── session.py               # Session 모델 (Refresh Token 저장)
└── core/
    └── config.py                # JWT_SECRET, OAuth 설정
```

---

## 환경 변수

```env
# JWT
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# OAuth Providers
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
KAKAO_CLIENT_ID=...
KAKAO_CLIENT_SECRET=...
```
