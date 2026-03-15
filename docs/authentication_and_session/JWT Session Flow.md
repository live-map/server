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

**1. Frontend sends the HTTP request:**

```typescript
// lib/auth/tokens.ts — buildAuthHeaders()
headers["Authorization"] = `Bearer ${accessToken}`;
headers["X-Refresh-Token"] = refreshToken;
```

```
POST /api/v1/posts HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjbHh...
X-Refresh-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjbHh...
Content-Type: application/json

{
  "title": "Best pizza in Seoul?",
  "content": "Looking for recommendations near Gangnam."
}
```

**2. TokenRefreshMiddleware receives the request first (ASGI layer):**

```python
# app/api/v1/auth/refresh_middleware.py
# Middleware decodes the access token to check if it's valid
payload = pyjwt.decode(access_token, settings.JWT_SECRET, ...)
# → Success: type="access", not expired
# → Pass through to the next layer (JWT Guard)
```

**3. FastAPI resolves `CurrentUser` dependency before the endpoint runs:**

The `create_post` endpoint declares `current_user: CurrentUser` as a parameter.
FastAPI sees this and calls `get_current_user()` automatically via `Depends()`.

```python
# app/api/v1/auth/jwt_guard.py — get_current_user()

# Extract token from header or cookie
token = token_from_header or token_from_cookie
# → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjbHh..."

# Decode and validate
payload = decode_token(token)
# → { "sub": "clx7abc123", "email": "kim@gmail.com", "name": "Kim",
#      "role": "USER", "type": "access", "iat": 1710000000, "exp": 1710001800 }

# Verify it's an access token (not a refresh token)
if payload.get("type") != "access":
    raise HTTPException(401)

# Return structured payload
return JWTPayload.from_dict(payload)
# → JWTPayload(user_id="clx7abc123", email="kim@gmail.com", name="Kim", role="USER")
```

**4. The endpoint receives the validated user and creates the post:**

```python
# app/api/v1/post/controller.py
async def create_post(
    data: PostCreate,
    current_user: CurrentUser,  # ← JWTPayload injected by FastAPI
    postService: Annotated[PostService, Depends(get_post_service)],
):
    post = await postService.create_post_without_commit(
        user_id=current_user.user_id,  # ← "clx7abc123" from the JWT
        title=data.title,
        content=data.content,
    )
```

**5. Backend returns the response:**

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

The key point: **the backend never queries the DB to authenticate the user**. The user's identity (`user_id`, `email`, `name`, `role`) is entirely extracted from the JWT payload. The token itself is the proof of identity.

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
