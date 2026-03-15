# JWT Session Flow — Access Token & Refresh Token

## Overview

Grapoll uses **stateless JWT sessions**. After OAuth authentication, the backend issues two JWTs:

| Token | Purpose | Expiration | Storage |
|-------|---------|------------|---------|
| **Access Token** | Authenticate API requests | 30 minutes | `grapoll-access-token` cookie (httpOnly) |
| **Refresh Token** | Issue new access tokens without re-login | 30 days | `grapoll-refresh-token` cookie (httpOnly) |

Both tokens are **stateless JWTs** — no server-side session storage or DB lookup needed.

---

## Token Structure

### Access Token Payload

```json
{
  "sub": "cuid_user_id",
  "email": "user@example.com",
  "name": "John",
  "role": "USER",
  "type": "access",
  "iat": 1710000000,
  "exp": 1710001800
}
```

### Refresh Token Payload

```json
{
  "sub": "cuid_user_id",
  "email": "user@example.com",
  "name": "John",
  "role": "USER",
  "type": "refresh",
  "iat": 1710000000,
  "exp": 1712592000
}
```

Both tokens carry the same user claims. The only differences are `type` ("access" vs "refresh") and `exp` (30 min vs 30 days). Signed with **HS256** using `JWT_SECRET`.

**Source:** `app/api/v1/auth/jwt.py`

---

## Full Session Lifecycle

```
┌──────────┐       ┌──────────────┐       ┌──────────────┐
│  Browser  │       │  Next.js     │       │  FastAPI      │
│  (Client) │       │  (Frontend)  │       │  (Backend)    │
└─────┬─────┘       └──────┬───────┘       └──────┬────────┘
      │                     │                      │
      │  ① OAuth Login Complete                    │
      │  ←─────────────────────────────────────────│  Backend returns:
      │                     │                      │  { access_token, refresh_token }
      │                     │                      │
      │  ② Set httpOnly Cookies                    │
      │  ←──────────────────│                      │
      │  grapoll-access-token  (30 min)            │
      │  grapoll-refresh-token (30 days)           │
      │                     │                      │
      │  ③ API Request                             │
      │  ──────────────────────────────────────────→
      │  Authorization: Bearer <access_token>      │
      │  X-Refresh-Token: <refresh_token>          │
      │                     │                      │
      │  ④ JWT Guard validates access token        │
      │  ←─────────────────────────────────────────│  200 OK + data
      │                     │                      │
      │         ... 30 minutes later ...           │
      │                     │                      │
      │  ⑤ API Request (access token expired)      │
      │  ──────────────────────────────────────────→
      │  Authorization: Bearer <expired_token>     │
      │  X-Refresh-Token: <refresh_token>          │
      │                     │                      │
      │  ⑥ Middleware auto-refreshes               │
      │  ←─────────────────────────────────────────│  200 OK + data
      │                     │                      │  X-New-Access-Token: <new_token>
      │                     │                      │
      │  ⑦ Update cookie with new access token     │
      │  ←──────────────────│                      │
      │                     │                      │
      │         ... 30 days later ...              │
      │                     │                      │
      │  ⑧ Both tokens expired                     │
      │  ──────────────────────────────────────────→
      │  ←─────────────────────────────────────────│  401 Unauthorized
      │                     │                      │
      │  ⑨ Redirect to login                       │
      │  ←──────────────────│                      │
      │                     │                      │
```

---

## Step-by-Step Breakdown

### Step ①②: Token Issuance & Storage

After OAuth authentication completes, the backend issues both tokens. The frontend stores them as **httpOnly cookies**.

**Backend — Token Creation:**
```python
# app/api/v1/auth/service.py — AuthService.authenticate_oauth()
access_token = create_access_token(
    user_id=user.id, email=user.email, name=user.name, role=user.role,
)
refresh_token = create_refresh_token(
    user_id=user.id, email=user.email, name=user.name, role=user.role,
)
```

**Frontend — Cookie Storage:**
```typescript
// app/api/auth/callback/[provider]/route.ts
response.cookies.set(ACCESS_COOKIE, data.access_token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: 30 * 60,           // 30 minutes
});
response.cookies.set(REFRESH_COOKIE, data.refresh_token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: 30 * 24 * 60 * 60, // 30 days
});
```

### Step ③④: Normal API Request

Example: A user creates a post in the community.

#### 1. Frontend builds and sends the HTTP request

The frontend reads tokens from httpOnly cookies (server-side via Next.js `cookies()`) and attaches them as headers before sending to the backend.

```typescript
// lib/auth/tokens.ts — buildAuthHeaders()
headers["Authorization"] = `Bearer ${accessToken}`;
headers["X-Refresh-Token"] = refreshToken;
```

The actual HTTP request that leaves the Next.js server:

```
POST /api/v1/posts HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjbHg3YWJjMTIzIiwiZW1haWwiOiJraW1AZ21haWwuY29tIiwibmFtZSI6IktpbSIsInJvbGUiOiJVU0VSIiwidHlwZSI6ImFjY2VzcyIsImlhdCI6MTcxMDAwMDAwMCwiZXhwIjoxNzEwMDAxODAwfQ.xxxxx
X-Refresh-Token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjbHg3YWJjMTIzIiwidHlwZSI6InJlZnJlc2giLCJleHAiOjE3MTI1OTIwMDB9.yyyyy
Content-Type: application/json

{
  "title": "Best pizza in Seoul?",
  "content": "Looking for recommendations near Gangnam."
}
```

#### 2. Request enters the FastAPI middleware stack

Before the request reaches any endpoint, it passes through a chain of middlewares registered in `app/main.py`. The order they are registered determines the order they execute:

```python
# app/main.py
app.add_middleware(CORSMiddleware, ...)         # ① registered first
app.add_middleware(TokenRefreshMiddleware)       # ② registered second
app.add_middleware(SlowAPIMiddleware)            # ③ registered third
```

**ASGI middleware executes in reverse registration order** — the last registered middleware runs first (outermost layer), wrapping inward. So the actual execution order for an incoming request is:

```
Request arrives
    │
    ▼
③ SlowAPIMiddleware      ← rate limiting check (60 req/min)
    │
    ▼
② TokenRefreshMiddleware  ← token validation / auto-refresh
    │
    ▼
① CORSMiddleware          ← CORS headers
    │
    ▼
   FastAPI Router          ← endpoint + Depends() resolution
```

#### 3. TokenRefreshMiddleware processes the request

The middleware is a pure ASGI middleware. It receives the raw ASGI `scope` (containing path and headers) before FastAPI even parses the request body.

```python
# app/api/v1/auth/refresh_middleware.py — TokenRefreshMiddleware.__call__()

# Step A: Check if this path should skip token processing
path = scope["path"]  # → "/api/v1/posts"
if self._should_skip(path):  # skips /api/v1/auth/*, /health, /docs
    await self.app(scope, receive, send)
    return
# → "/api/v1/posts" doesn't match any skip prefix, so continue

# Step B: Parse cookies and extract tokens from headers
headers = dict(scope.get("headers", []))
cookies = self._parse_cookies(headers)

access_token = self._get_access_token(headers, cookies)
# → Checks Authorization header first: "Bearer eyJhbG..." → extracts "eyJhbG..."
# → Falls back to grapoll-access-token cookie if no header

refresh_token = self._get_refresh_token(headers, cookies)
# → Checks X-Refresh-Token header first: "eyJhbG..."
# → Falls back to grapoll-refresh-token cookie if no header

# Step C: Validate the access token
try:
    payload = pyjwt.decode(
        access_token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") == "access":
        # ✅ Access token is valid and not expired
        # Pass the request through to the next layer unchanged
        await self.app(scope, receive, send)
        return
except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
    pass  # token is expired or invalid — will attempt refresh below
```

In this case (normal request with a valid access token), the middleware calls `await self.app(scope, receive, send)` — passing the request to the next middleware in the chain, untouched. Eventually it reaches FastAPI's router.

#### 4. FastAPI resolves `CurrentUser` dependency via the JWT Guard

The `create_post` endpoint declares `current_user: CurrentUser` as a parameter:

```python
# app/api/v1/post/controller.py
async def create_post(
    data: PostCreate,
    current_user: CurrentUser,  # ← triggers dependency resolution
    postService: Annotated[PostService, Depends(get_post_service)],
):
```

`CurrentUser` is a type alias:

```python
# app/api/v1/auth/jwt_guard.py
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]
```

So FastAPI automatically calls `get_current_user()` before the endpoint runs:

```python
# app/api/v1/auth/jwt_guard.py — get_current_user()

# Extract token from Authorization header or cookie (same token the middleware already validated)
token = token_from_header or token_from_cookie
# → "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjbHg3YWJjMTIzIi..."

# Decode the JWT and extract the payload
payload = decode_token(token)
# → {
#     "sub": "clx7abc123",
#     "email": "kim@gmail.com",
#     "name": "Kim",
#     "role": "USER",
#     "type": "access",
#     "iat": 1710000000,
#     "exp": 1710001800
#   }

# Verify it's an access token (reject refresh tokens)
if payload.get("type") != "access":
    raise HTTPException(status_code=401, detail="Invalid token type.")

# Convert dict → structured dataclass
return JWTPayload.from_dict(payload)
# → JWTPayload(user_id="clx7abc123", email="kim@gmail.com", name="Kim", role="USER")
```

> Note: The token is decoded **twice** — once by the middleware (to decide whether to refresh) and once by the JWT Guard (to extract the user). This is intentional because the middleware operates at the ASGI layer (before FastAPI) and has no way to pass the decoded payload to the FastAPI dependency system.

#### 5. The endpoint uses the validated user to create the post

```python
# app/api/v1/post/controller.py
post = await postService.create_post_without_commit(
    user_id=current_user.user_id,  # ← "clx7abc123" extracted from JWT
    title=data.title,              # ← "Best pizza in Seoul?"
    content=data.content,          # ← "Looking for recommendations near Gangnam."
)
```

#### 6. Backend returns the response

```
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "clx9xyz789",
  "title": "Best pizza in Seoul?",
  "content": "Looking for recommendations near Gangnam.",
  "authorId": "clx7abc123",
  "createdAt": "2026-03-13T12:00:00Z"
}
```

The response travels back through the middleware stack in reverse (CORSMiddleware adds CORS headers, etc.) and is sent to the frontend.

**Key point: the backend never queries the DB to authenticate the user.** The user's identity (`user_id`, `email`, `name`, `role`) is entirely extracted from the JWT payload. The signed token itself is the proof of identity.

### Step ⑤⑥⑦: Auto-Refresh (Token Expired)

When the access token expires, the **TokenRefreshMiddleware** (ASGI middleware) intercepts the request before it reaches the JWT Guard.

```python
# app/api/v1/auth/refresh_middleware.py — TokenRefreshMiddleware

# 1. Try to decode the access token
payload = pyjwt.decode(access_token, ...)
# → Raises ExpiredSignatureError

# 2. Access token expired — decode refresh token instead
refresh_payload = decode_refresh_token(refresh_token)

# 3. Create a new access token from refresh token claims
new_access_token = create_access_token(
    user_id=refresh_payload["sub"],
    email=refresh_payload.get("email"),
    name=refresh_payload.get("name"),
    role=refresh_payload.get("role", "USER"),
)

# 4. Inject new token into the request's Authorization header
scope["headers"] = self._replace_auth_header(scope["headers"], new_access_token)

# 5. Add new token to response header for the frontend to update its cookie
headers.append((b"x-new-access-token", new_access_token.encode()))
```

**Frontend — Handling the New Token:**
```typescript
// lib/auth/tokens.ts — handleTokenRefreshResponse()
const newToken = res.headers.get("x-new-access-token");
if (newToken) {
  await updateAccessTokenCookie(newToken);
}
```

This is called automatically in the OpenAPI client (`config/openapi-runtime.ts`) and in `apiFetch()` (`lib/api.ts`).

### Step ⑧⑨: Session Expiry (Refresh Token Expired)

When both tokens are expired, the middleware cannot refresh, and the JWT Guard returns 401. The frontend clears cookies and redirects to login.

```typescript
// proxy.ts — Route protection
const isLoggedIn = hasAccessToken || hasRefreshToken;

if (isProtectedRoute(pathname) && !isLoggedIn) {
  return NextResponse.redirect(new URL(`/auth/signin?callbackUrl=${callbackUrl}`, nextUrl));
}
```

---

## Logout

Logout is a **client-side operation**. The backend's logout endpoint is a no-op because tokens are stateless (no server-side session to revoke).

**Frontend:**
```typescript
// app/api/auth/logout/route.ts
response.cookies.delete(ACCESS_COOKIE);
response.cookies.delete(REFRESH_COOKIE);
```

**Backend:**
```python
# app/api/v1/auth/controller.py
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest):
    pass  # No-op. Client clears cookies.
```

The access token remains technically valid until it expires (30 min), but since the cookie is deleted, the browser no longer sends it.

---

## Token Validation Summary

```
                       ┌─────────────────────────┐
                       │   Incoming API Request   │
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │  TokenRefreshMiddleware   │
                       │  (ASGI layer)             │
                       └────────────┬─────────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                   │
          Access token         Access token         No access token
           is valid             expired              at all
                  │                 │                   │
                  │          ┌──────▼──────┐           │
                  │          │ Has refresh  │           │
                  │          │   token?     │           │
                  │          └──────┬───────┘           │
                  │           Yes   │    No             │
                  │                 │     │             │
                  │          ┌──────▼──────┐           │
                  │          │ Decode       │           │
                  │          │ refresh JWT  │           │
                  │          └──────┬───────┘           │
                  │          Valid   │  Invalid/Expired │
                  │                 │     │             │
                  │          ┌──────▼──────┐           │
                  │          │ Create new   │           │
                  │          │ access token │           │
                  │          │ + inject     │           │
                  │          └──────┬───────┘           │
                  │                 │                   │
                  ▼                 ▼                   ▼
           ┌──────────────────────────────────────────────┐
           │              JWT Guard                        │
           │  (FastAPI Depends)                            │
           │                                               │
           │  Valid access token → JWTPayload → 200        │
           │  No/invalid token  → 401 Unauthorized         │
           └───────────────────────────────────────────────┘
```

---

## Security Considerations

| Feature | Implementation |
|---------|---------------|
| **httpOnly cookies** | Tokens cannot be accessed by JavaScript (XSS protection) |
| **Secure flag** | In production, cookies only sent over HTTPS |
| **SameSite=Lax** | Cookies not sent on cross-site POST requests (CSRF protection) |
| **Short access token lifetime** | 30 minutes — limits damage if token is leaked |
| **HS256 signing** | Tokens cannot be forged without `JWT_SECRET` |
| **Type claim validation** | Refresh tokens rejected as access tokens and vice versa |

### Limitation: No Server-Side Revocation

Since both tokens are stateless JWTs, the backend cannot revoke a specific token before its natural expiration. After logout, the access token remains valid for up to 30 minutes. To support instant revocation, a token blacklist (Redis or DB) would be needed.

---

## Related Files

| File | Role |
|------|------|
| `app/api/v1/auth/jwt.py` | Token creation (`create_access_token`, `create_refresh_token`) and decoding |
| `app/api/v1/auth/jwt_guard.py` | Token validation dependency (`get_current_user`, `CurrentUser`) |
| `app/api/v1/auth/refresh_middleware.py` | ASGI middleware for auto-refreshing expired access tokens |
| `app/api/v1/auth/service.py` | `AuthService` — issues tokens after OAuth authentication |
| `app/api/v1/auth/controller.py` | `/auth/refresh` and `/auth/logout` endpoints |
| `app/core/config.py` | `JWT_SECRET`, `JWT_ALGORITHM`, expiration settings |
| **Frontend** | |
| `lib/auth/tokens.ts` | Cookie read/write, `buildAuthHeaders()`, `handleTokenRefreshResponse()` |
| `app/api/auth/callback/[provider]/route.ts` | Sets cookies after OAuth callback |
| `app/api/auth/logout/route.ts` | Clears cookies on logout |
| `config/openapi-runtime.ts` | Injects tokens into OpenAPI client requests |
| `proxy.ts` | Route protection — redirects unauthenticated users |
