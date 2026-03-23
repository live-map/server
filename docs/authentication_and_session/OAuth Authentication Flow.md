# OAuth 2.0 Authorization Code Flow - Grapoll

이 문서는 Grapoll 프로젝트의 OAuth 2.0 인증 흐름을 설명합니다.
아래 다이어그램의 각 단계(1~14)가 클라이언트(Next.js)와 서버(FastAPI) 코드에서 어떻게 구현되어 있는지 매핑합니다.

---

## 아키텍처 개요

| 다이어그램 Actor      | 역할                                      | Grapoll 구현                                           |
| --------------------- | ----------------------------------------- | ------------------------------------------------------ |
| **사용자**            | 서비스를 이용하는 최종 사용자               | 브라우저 사용자                                        |
| **서비스 Client**     | 사용자에게 서비스를 제공하는 애플리케이션   | Next.js 프론트엔드 (port 3000) + FastAPI 백엔드 (port 8000) |
| **Authorization Server** | 인증 및 Access Token 발급을 담당하는 서버 | Google: `accounts.google.com`, `oauth2.googleapis.com` / Kakao: `kauth.kakao.com` |
| **Resource Server**   | Access Token으로 보호된 사용자 데이터 제공  | Google: `www.googleapis.com/oauth2/v3/userinfo` / Kakao: `kapi.kakao.com/v2/user/me` |

### 전체 흐름 다이어그램

다이어그램의 4개 Actor를 그대로 반영합니다.
**서비스 Client**는 Next.js 프론트엔드와 FastAPI 백엔드를 합친 개념입니다.
**Authorization Server**와 **Resource Server**는 동일 제공자(Google/Kakao)의 서로 다른 서버입니다.

```
┌──────────┐   ┌──────────────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│          │   │      서비스 Client        │   │  Authorization   │   │    Resource      │
│  사용자   │   │ Next.js     FastAPI      │   │     Server       │   │     Server       │
│ (Browser)│   │ (3000)      (8000)       │   │ (Google/Kakao    │   │ (Google/Kakao    │
│          │   │                          │   │  인증 서버)       │   │  프로필 API)     │
└────┬─────┘   └──────┬──────────┬────────┘   └────────┬─────────┘   └────────┬─────────┘
     │                │          │                     │                      │
     │ [1] 서비스 접근 │          │                     │                      │
     │───────────────>│          │                     │                      │
     │                │          │                     │                      │
     │ [2] Client ID, │Redirect_URI                    │                      │
     │  (인가 URL 요청)│─────────>│                     │                      │
     │                │<─────────│ (인가 URL 반환)      │                      │
     │                │          │                     │                      │
     │ [3] 로그인 페이지 요청 (Client ID, Redirect URI)  │                      │
     │────────────────────────────────────────────────>│                      │
     │                │          │                     │                      │
     │ [4] 로그인 페이지 제공                            │                      │
     │<────────────────────────────────────────────────│                      │
     │                │          │                     │                      │
     │ [5] ID/PW 입력 │          │                     │                      │
     │────────────────────────────────────────────────>│                      │
     │                │          │                     │                      │
     │ [6] Authorization Code 발급                      │                      │
     │                │          │                     │                      │
     │ [7] Redirect_URI로 Authorization Code 전달       │                      │
     │<────────────────────────────────────────────────│                      │
     │                │          │                     │                      │
     │ /callback?code=│          │                     │                      │
     │───────────────>│          │                     │                      │
     │                │─────────>│                     │                      │
     │                │          │                     │                      │
     │                │          │ [8] Authorization Code로 Access Token 요청  │
     │                │          │────────────────────>│                      │
     │                │          │                     │                      │
     │                │          │ [9] Access Token 발급│                      │
     │                │          │<────────────────────│                      │
     │                │          │                     │                      │
     │                │          │ [12] Access Token으로 API 호출              │
     │                │          │───────────────────────────────────────────>│
     │                │          │                     │                      │
     │                │          │ [13] 사용자 정보 검증 및 제공                │
     │                │          │<───────────────────────────────────────────│
     │                │          │                     │                      │
     │ [10] 인증 완료  │<─────────│ (JWT 발급 + 반환)   │                      │
     │   (쿠키 저장)   │          │                     │                      │
     │<───────────────│          │                     │                      │
     │                │          │                     │                      │
     │ [11] 서비스 요청│          │                     │                      │
     │───────────────>│─────────>│                     │                      │
     │                │          │                     │                      │
     │ [14] 서비스 제공│<─────────│                     │                      │
     │<───────────────│          │                     │                      │
```

**핵심 구분:**
- **Authorization Server** (Steps 3-9): 인증 및 토큰 발급을 담당
  - Google: `accounts.google.com`, `oauth2.googleapis.com`
  - Kakao: `kauth.kakao.com`
- **Resource Server** (Steps 12-13): 사용자 데이터 제공을 담당
  - Google: `www.googleapis.com/oauth2/v3/userinfo`
  - Kakao: `kapi.kakao.com/v2/user/me`

---

## Step 1. 서비스 접근 및 이용 시도

> 사용자가 서비스에 접근하여 로그인을 시도한다.

사용자가 앱에 방문하여 로그인 버튼을 클릭합니다. 두 가지 진입점이 있습니다:

**로그인 페이지** — `client/app/auth/signin/page.tsx`

```tsx
<OAuthButton provider="google" />
<OAuthButton provider="kakao" />
```

**로그인 모달** — `client/components/auth/login-modal.tsx`

```tsx
const { openLoginModal } = useLoginModal();
openLoginModal("로그인이 필요합니다");
```

로그인 버튼 컴포넌트 — `client/components/auth/oauth-button.tsx`

```tsx
export function OAuthButton({ provider, callbackUrl }: OAuthButtonProps) {
  return (
    <form action={() => signInWithOAuth(provider, callbackUrl)}>
      <Button type="submit" variant="outline" className="w-full">
        {/* Google/Kakao 아이콘 */}
      </Button>
    </form>
  );
}
```

---

## Step 2. Client ID, Redirect_URI

> 서비스 Client가 Client ID와 Redirect URI를 준비하여 Authorization Server에 전달할 준비를 한다.

사용자가 OAuth 버튼을 클릭하면, Next.js **Server Action**이 실행됩니다:

**`client/app/actions/auth.ts`** — `signInWithOAuth()`

```typescript
export async function signInWithOAuth(
  provider: "google" | "kakao",
  callbackUrl = "/"
): Promise<void> {
  // 1. 로그인 후 돌아갈 URL을 쿠키에 저장
  const cookieStore = await cookies();
  cookieStore.set("auth-callback-url", callbackUrl, {
    path: "/", maxAge: 600, httpOnly: true, sameSite: "lax",
  });

  // 2. redirect_uri 생성 (OAuth 제공자가 인증 후 리다이렉트할 URL)
  const redirectUri = `${FRONTEND_URL}/api/auth/callback/${provider}`;

  // 3. FastAPI 백엔드에 인가 URL 요청
  const res = await fetch(
    `${API_BASE}/api/v1/auth/oauth/${provider}/authorize?redirect_uri=${encodeURIComponent(redirectUri)}`
  );

  // 4. 인가 URL로 리다이렉트
  const data = await res.json();
  redirect(data.url);
}
```

백엔드가 Client ID와 Redirect URI를 포함한 인가 URL을 생성합니다:

**`server/app/api/v1/auth/controller.py`** — `get_oauth_authorize_url()`

```python
@router.get("/oauth/{provider}/authorize")
async def get_oauth_authorize_url(provider: str, redirect_uri: str = Query(...)):
    state = secrets.token_urlsafe(32)  # CSRF 방지용 state
    url = get_authorization_url(provider, redirect_uri, state)
    return AuthUrlResponse(url=url, state=state)
```

**`server/app/api/v1/auth/lib/oauth.py`** — OAuth 제공자 설정

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

## Step 3. 로그인 페이지 요청 (Client ID, Redirect URI)

> 서비스 Client가 Authorization Server에 Client ID와 Redirect URI를 보내 로그인 페이지를 요청한다.

프론트엔드가 브라우저를 인가 URL로 **리다이렉트**합니다. Google의 경우:

```
https://accounts.google.com/o/oauth2/v2/auth
  ?client_id=762946054573-...
  &redirect_uri=http://localhost:3000/api/auth/callback/google
  &scope=openid email profile
  &response_type=code
  &state=<csrf_token>
```

`signInWithOAuth()` 함수 내의 `redirect(data.url)` 호출이 이 리다이렉트를 수행합니다.

**Authlib**의 `AsyncOAuth2Client`가 URL을 생성합니다:

```python
def get_authorization_url(provider: str, redirect_uri: str, state: str) -> str:
    config = get_provider_config(provider)
    client = create_oauth_client(provider, redirect_uri)
    url, _ = client.create_authorization_url(config["authorize_url"], state=state)
    return url
```

---

## Step 4. 로그인 페이지 제공

> Authorization Server가 사용자에게 로그인 페이지를 제공한다.

Google/Kakao가 자체 로그인 및 동의 화면을 사용자에게 표시합니다.
이 단계는 OAuth 제공자가 처리하므로 **프로젝트 코드에 해당 구현이 없습니다**.

---

## Step 5. ID / PW 입력

> 사용자가 Authorization Server의 로그인 페이지에서 자격 증명을 입력한다.

사용자가 Google/Kakao 페이지에서 자격 증명을 입력합니다.
이 단계도 OAuth 제공자 서버에서 처리되므로 **프로젝트 코드에 해당 구현이 없습니다**.

---

## Step 6. Authorization Code 발급

> Authorization Server가 사용자 인증 후 Authorization Code를 발급한다.

사용자가 인증에 성공하면, Google/Kakao가 **authorization code**를 생성합니다.
OAuth 제공자의 내부 동작이므로 **프로젝트 코드에 해당 구현이 없습니다**.

---

## Step 7. Redirect_URI로 Authorization Code 전달

> Authorization Server가 Redirect URI로 사용자 브라우저를 리다이렉트하며 Authorization Code를 전달한다.

OAuth 제공자가 브라우저를 다음 URL로 리다이렉트합니다:

```
http://localhost:3000/api/auth/callback/google?code=XXXX&state=YYYY
```

이 요청은 Next.js API Route에서 처리됩니다:

**`client/app/api/auth/callback/[provider]/route.ts`**

```typescript
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
) {
  const { provider } = await params;
  const searchParams = request.nextUrl.searchParams;

  // OAuth 제공자가 전달한 authorization code와 state
  const code = searchParams.get("code");
  const state = searchParams.get("state");

  // 로그인 전 사용자가 있던 페이지 (Step 2에서 쿠키에 저장)
  const callbackUrl = request.cookies.get("auth-callback-url")?.value || "/";

  if (!code) {
    return NextResponse.redirect(new URL("/auth/signin?error=no_code", FRONTEND_URL));
  }

  // ... Step 8로 이어짐
}
```

---

## Step 8. Authorization Code로 Access Token 요청

> 서비스 Client가 Authorization Code를 사용하여 Authorization Server에 Access Token을 요청한다.

Next.js 콜백 라우트가 **authorization code를 FastAPI 백엔드에 전달**하고,
백엔드가 이를 OAuth 제공자와 교환합니다:

**Client → Backend** (`client/app/api/auth/callback/[provider]/route.ts` 에서):

```typescript
const res = await fetch(`${API_BASE}/api/v1/auth/oauth/${provider}/callback`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    code,          // authorization code
    state,         // CSRF 방지용 state
    redirect_uri: redirectUri,
  }),
});
```

**Backend Controller** — `oauth_callback` 엔드포인트가 `AuthService`를 `Depends()`로 주입받아 호출합니다:

```python
# server/app/api/v1/auth/controller.py
@router.post("/oauth/{provider}/callback", response_model=AuthResponse)
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    service: AuthService = Depends(),  # FastAPI가 AuthService 인스턴스를 자동 생성
):
    result = await service.authenticate_oauth(provider, body.code, body.redirect_uri)
    return AuthResponse(**result)
```

**Backend Service** — `AuthService.authenticate_oauth()`가 OAuth 제공자와 token을 교환합니다:

```python
# server/app/api/v1/auth/service.py
class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)) -> None:
        self.repo = AuthRepository(db)

    async def authenticate_oauth(self, provider, code, redirect_uri) -> dict:
        # Step 8: Authorization code를 OAuth 제공자 token으로 교환
        oauth_tokens = await exchange_code_for_token(provider, code, redirect_uri)
        # ... Step 9, 12, 13으로 이어짐
```

**`server/app/api/v1/auth/lib/oauth.py`** — Authlib을 사용한 token 교환:

```python
async def exchange_code_for_token(provider: str, code: str, redirect_uri: str) -> dict:
    config = get_provider_config(provider)
    client = create_oauth_client(provider, redirect_uri)
    token = await client.fetch_token(config["token_url"], code=code)
    return dict(token)
```

내부적으로 Authlib이 OAuth 제공자의 token URL에 POST 요청을 보냅니다:
- Google: `POST https://oauth2.googleapis.com/token`
- Kakao: `POST https://kauth.kakao.com/oauth/token`

요청 본문: `code`, `client_id`, `client_secret`, `redirect_uri`, `grant_type=authorization_code`

---

## Step 9. Access Token 발급

> Authorization Server가 Access Token을 발급한다.

OAuth 제공자가 **제공자의 access token**을 반환합니다:

```json
{
  "access_token": "ya29.a0...",
  "refresh_token": "...",
  "expires_at": 1234567890,
  "token_type": "Bearer",
  "id_token": "..."
}
```

이 토큰들은 `accounts` 테이블에 저장됩니다 (향후 제공자 API 호출에 사용 가능):

**`server/app/api/v1/auth/repository.py`** — `AuthRepository.create_account()`

```python
async def create_account(self, user_id, provider, provider_account_id, oauth_tokens) -> Account:
    account = Account(
        id=generate_cuid(),
        user_id=user_id,
        type="oauth",
        provider=provider,
        provider_account_id=provider_account_id,
        access_token=oauth_tokens.get("access_token"),    # 제공자의 access token
        refresh_token=oauth_tokens.get("refresh_token"),  # 제공자의 refresh token
        expires_at=oauth_tokens.get("expires_at"),
        token_type=oauth_tokens.get("token_type"),
        scope=oauth_tokens.get("scope"),
        id_token=oauth_tokens.get("id_token"),
    )
    self.session.add(account)
    await self.session.commit()
    return account
```

---

## Step 10. 인증 완료 및 로그인 성공

> 서비스 Client가 인증을 완료하고 사용자에게 로그인 성공을 알린다.

제공자의 token을 받은 후, 백엔드가 다음을 수행합니다:

### 10-1. 사용자 프로필 조회 (Step 12, 13이 여기서 실행)

```python
# server/app/api/v1/auth/service.py — AuthService.authenticate_oauth()
profile = await fetch_user_profile(provider, oauth_tokens["access_token"])
```

### 10-2. 사용자 조회/생성

`AuthService`가 `AuthRepository`의 메서드를 호출하여 사용자를 조회하거나 생성합니다.
Service는 비즈니스 로직(언제, 왜 호출하는지)을 담당하고, Repository는 DB 접근(어떻게 조회/생성하는지)을 담당합니다.

```python
# server/app/api/v1/auth/service.py — AuthService.authenticate_oauth()
provider_account_id = profile["provider_account_id"]

# 1차: OAuth 계정으로 사용자 + 계정을 한 번에 조회 (단일 JOIN 쿼리)
result = await self.repo.find_user_and_account_by_oauth(provider, provider_account_id)

if result:
    # 기존 사용자 → 제공자 OAuth 토큰만 갱신
    (user, account) = result
    await self.repo.update_account_tokens(account, oauth_tokens)
else:
    # 2차: 이메일로 기존 사용자 검색 (계정 연결)
    if profile.get("email"):
        user = await self.repo.find_user_by_email(profile["email"])
        if user:
            logger.info(f"Linking new OAuth account to existing user: {user.id} ({provider})")
        else:
            user = await self.repo.create_user(profile)
    else:
        # 이메일 없는 경우 새 사용자 생성
        user = await self.repo.create_user(profile)
    # 새 OAuth 계정을 사용자에 연결
    await self.repo.create_account(user.id, provider, provider_account_id, oauth_tokens)
```

사용자 조회 우선순위:
1. OAuth 계정 (provider + provider_account_id)으로 기존 사용자 + 계정 검색
2. 같은 이메일의 기존 사용자에 새 OAuth 계정 연결
3. 새 사용자 + OAuth 계정 생성

### 10-3. 앱 자체 JWT 발급

**`server/app/api/v1/auth/jwt.py`**

```python
def create_access_token(user_id, email, name, role) -> str:
    payload = {
        "sub": user_id, "email": email, "name": name, "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=30),  # 30분
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(user_id, email, name, role) -> str:
    payload = {
        "sub": user_id, "email": email, "name": name, "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=30),  # 30일
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
```

### 10-4. 프론트엔드에 토큰 반환

백엔드 응답:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "user": { "id": "...", "email": "...", "name": "...", "image": "...", "role": "USER" }
}
```

### 10-5. httpOnly 쿠키에 토큰 저장

**`client/app/api/auth/callback/[provider]/route.ts`**

```typescript
// Access token — 30분 만료
response.cookies.set(ACCESS_COOKIE, data.access_token, {
  httpOnly: true,   // JS에서 접근 불가 (XSS 방어)
  secure: process.env.NODE_ENV === "production",  // HTTPS only
  sameSite: "lax",  // CSRF 방어 + OAuth 리다이렉트 허용
  path: "/",
  maxAge: 30 * 60,  // 30분
});

// Refresh token — 30일 만료
response.cookies.set(REFRESH_COOKIE, data.refresh_token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: 30 * 24 * 60 * 60,  // 30일
});
```

쿠키 이름:
| 환경 | Access Token | Refresh Token |
|------|-------------|---------------|
| Development | `grapoll-access-token` | `grapoll-refresh-token` |
| Production | `__Secure-grapoll-access-token` | `__Secure-grapoll-refresh-token` |

### 10-6. 원래 페이지로 리다이렉트

```typescript
const callbackUrl = request.cookies.get("auth-callback-url")?.value || "/";
const response = NextResponse.redirect(new URL(callbackUrl, FRONTEND_URL));
response.cookies.delete("auth-callback-url");  // 임시 쿠키 삭제
```

---

## Step 11. 서비스 요청

> 인증된 사용자가 서비스를 요청한다.

로그인이 완료된 후, 모든 API 요청에 JWT가 자동으로 포함됩니다.

### 클라이언트 측 인증 상태 관리

**`client/lib/auth/auth-context.tsx`** — React Context

```typescript
export function useAuth() {
  // user: 현재 인증된 사용자 정보 (or null)
  // status: "loading" | "authenticated" | "unauthenticated"
  // refreshAuth(): 인증 상태 수동 갱신
  // logout(): 로그아웃
}
```

`AuthProvider`는 마운트 시 `/api/auth/me`를 호출하여 인증 상태를 확인합니다.

### 서버 측 인증 상태 관리

**`client/lib/auth/session.ts`** — Server Component용

```typescript
export async function auth(): Promise<ServerSession | null> {
  const headers = await buildAuthHeaders();
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, { headers, cache: "no-store" });
  await handleTokenRefreshResponse(res);  // 토큰 갱신 응답 처리
  // ...
}
```

### 요청 시 토큰 주입

**`client/lib/auth/tokens.ts`** — `buildAuthHeaders()`

```typescript
export async function buildAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  const accessToken = await getAccessToken();    // 쿠키에서 읽기
  const refreshToken = await getRefreshToken();  // 쿠키에서 읽기

  if (accessToken)  headers["Authorization"] = `Bearer ${accessToken}`;
  if (refreshToken) headers["X-Refresh-Token"] = refreshToken;
  return headers;
}
```

두 가지 API 호출 경로 모두 토큰을 자동 주입합니다:
- **OpenAPI 클라이언트** (`client/config/openapi-runtime.ts`) — `auth()` + custom `fetch()`
- **수동 fetch** (`client/lib/api.ts`) — `buildAuthHeaders()` 사용

---

## Step 12. Access Token으로 API 호출

> 서비스 Client가 Access Token을 사용하여 Resource Server의 API를 호출한다.

다이어그램에서 이 단계는 서비스 Client가 **Resource Server에 사용자 정보를 요청**하는 것입니다.
Grapoll에서는 Step 10 내부에서 백엔드가 이를 수행합니다:

**`server/app/api/v1/auth/lib/oauth.py`** — `fetch_user_profile()`

```python
async def fetch_user_profile(provider: str, access_token: str) -> dict:
    config = get_provider_config(provider)
    async with AsyncOAuth2Client(
        token={"access_token": access_token, "token_type": "Bearer"}
    ) as client:
        resp = await client.get(config["userinfo_url"])
        resp.raise_for_status()
        data = resp.json()
    # ...
```

호출 대상:
- Google: `GET https://www.googleapis.com/oauth2/v3/userinfo` + `Authorization: Bearer {token}`
- Kakao: `GET https://kapi.kakao.com/v2/user/me` + `Authorization: Bearer {token}`

---

## Step 13. Authorization Code 검증 및 서비스 제공

> Resource Server가 Access Token을 검증하고 사용자 정보를 제공한다.

Resource Server(Google/Kakao)가 access token을 검증하고 사용자 프로필을 반환합니다.
백엔드는 이를 **공통 형식으로 정규화**합니다:

```python
# Google 응답 정규화
if provider == "google":
    return {
        "provider_account_id": data["sub"],
        "email": data.get("email"),
        "name": data.get("name"),
        "image": data.get("picture"),
    }

# Kakao 응답 정규화
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

## Step 14. 서비스 제공

> 인증이 완료된 사용자에게 서비스를 제공한다.

로그인 이후의 모든 인증된 요청은 다음 흐름으로 처리됩니다:

### 14-1. 자동 토큰 갱신 미들웨어

**`server/app/api/v1/auth/refresh_middleware.py`** — `TokenRefreshMiddleware`

```
1. 인증 관련 경로는 건너뜀 (/api/v1/auth/*, /health, /docs 등)
2. Authorization 헤더 또는 쿠키에서 access token 추출
3. Access token 검증 시도
4. Access token이 만료되었지만 refresh token이 유효한 경우:
   - Refresh token의 claims로 새 access token 생성
   - 요청의 Authorization 헤더에 주입
   - 응답에 X-New-Access-Token 헤더 추가
5. 라우트 핸들러로 요청 전달
```

```python
class TokenRefreshMiddleware:
    async def __call__(self, scope, receive, send):
        # ... access token 검증 실패 시
        if refresh_token:
            refresh_payload = decode_refresh_token(refresh_token)
            new_access_token = create_access_token(
                user_id=refresh_payload["sub"],
                email=refresh_payload.get("email"),
                name=refresh_payload.get("name"),
                role=refresh_payload.get("role", "USER"),
            )
            # 요청 헤더에 새 토큰 주입
            scope["headers"] = self._replace_auth_header(scope["headers"], new_access_token)
```

프론트엔드에서 갱신된 토큰을 쿠키에 반영:

```typescript
// client/lib/auth/tokens.ts
export async function handleTokenRefreshResponse(res: Response): Promise<void> {
  const newToken = res.headers.get("x-new-access-token");
  if (newToken) {
    await updateAccessTokenCookie(newToken);
  }
}
```

### 14-2. 라우트 가드 (JWT Guard)

**`server/app/api/v1/auth/jwt_guard.py`**

세 가지 인증 수준의 의존성 주입:

```python
# 선택적 인증 — 비로그인 사용자도 접근 가능
CurrentUserOptional = Annotated[JWTPayload | None, Depends(get_current_user_optional)]

# 필수 인증 — 401 반환 if 미인증
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]

# 관리자 전용 — 403 반환 if 비관리자
CurrentAdmin = Annotated[JWTPayload, Depends(get_current_admin)]
```

사용 예시 (`server/app/api/v1/auth/controller.py`):

```python
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    return UserResponse(
        id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
    )
```

토큰 추출 순서:
1. `Authorization: Bearer <token>` 헤더
2. `grapoll-access-token` / `__Secure-grapoll-access-token` 쿠키

---

## 보안 설계

| 보안 항목 | 구현 방식 |
|-----------|----------|
| **XSS 방어** | httpOnly 쿠키 — JS에서 토큰 접근 불가 |
| **CSRF 방어** | `sameSite: "lax"` 쿠키 + OAuth state 파라미터 |
| **HTTPS 적용** | Production에서 `secure: true` + `__Secure-` 접두사 쿠키 |
| **토큰 만료** | Access: 30분 / Refresh: 30일 |
| **Secret 보호** | OAuth client_secret은 백엔드에서만 사용 (프론트엔드 노출 없음) |
| **토큰 타입 검증** | JWT의 `type` claim으로 access/refresh 구분 |

---

## 관련 파일 목록

### Server (FastAPI)

| 파일 | 역할 |
|------|------|
| `app/api/v1/auth/controller.py` | 인증 API 엔드포인트 (authorize, callback, refresh, logout, me) |
| `app/api/v1/auth/service.py` | `AuthService` 클래스 — 인증 비즈니스 로직 (Controller → Service → Repository) |
| `app/api/v1/auth/repository.py` | `AuthRepository` 클래스 — DB 접근 (사용자/계정 조회, 생성, 토큰 갱신) |
| `app/api/v1/auth/lib/oauth.py` | OAuth 제공자 설정 및 Authlib 클라이언트 |
| `app/api/v1/auth/jwt.py` | JWT 생성 및 검증 (HS256) |
| `app/api/v1/auth/jwt_guard.py` | FastAPI 인증 가드 (Depends 의존성 주입) |
| `app/api/v1/auth/refresh_middleware.py` | 자동 토큰 갱신 ASGI 미들웨어 |
| `app/api/v1/auth/dto/schemas.py` | 요청/응답 Pydantic 스키마 |
| `app/models/user.py` | User 모델 (SQLAlchemy) |
| `app/models/account.py` | Account 모델 — OAuth 계정 연결 |

### Client (Next.js)

| 파일 | 역할 |
|------|------|
| `app/actions/auth.ts` | `signInWithOAuth()` Server Action |
| `app/api/auth/callback/[provider]/route.ts` | OAuth 콜백 핸들러 (code → 백엔드 전달 → 쿠키 저장) |
| `app/api/auth/me/route.ts` | 클라이언트 측 인증 상태 확인 API |
| `app/api/auth/logout/route.ts` | 로그아웃 (쿠키 삭제) |
| `lib/auth/tokens.ts` | 쿠키 기반 토큰 관리 (읽기, 갱신, 헤더 빌드) |
| `lib/auth/auth-context.tsx` | 클라이언트 측 Auth Context (`useAuth` 훅) |
| `lib/auth/session.ts` | 서버 측 세션 확인 (`auth()` 함수) |
| `lib/auth/with-auth.ts` | 인증된 Server Action 래퍼 (`withAuth` HOF) |
| `components/auth/oauth-button.tsx` | OAuth 로그인 버튼 컴포넌트 |
| `components/auth/login-modal.tsx` | 로그인 모달 Context |

---

## 환경 변수

### Server (.env)

```bash
JWT_SECRET=              # HS256 서명 키 (openssl rand -hex 32)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

GOOGLE_CLIENT_ID=        # Google Cloud Console
GOOGLE_CLIENT_SECRET=    # Google Cloud Console
KAKAO_CLIENT_ID=         # Kakao Developers
KAKAO_CLIENT_SECRET=     # Kakao Developers

FRONTEND_URL=http://localhost:3000   # CORS, 쿠키 도메인
```

### Client (.env)

```bash
NEXT_PUBLIC_APP_URL=http://localhost:3000
API_URL=http://localhost:8000

GOOGLE_CLIENT_ID=        # OAuth 버튼 표시용 (선택)
GOOGLE_CLIENT_SECRET=    # 프론트엔드에서는 사용하지 않음
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
```
