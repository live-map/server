# TokenRefreshMiddleware

## What It Does

Automatically refreshes expired access tokens using the refresh token. When an access token expires, the middleware creates a new one from the refresh token's claims and injects it into the request — so the JWT Guard sees a valid token and the endpoint runs normally. The user never notices the token expired.

## Why Pure ASGI?

This middleware uses **pure ASGI** (not `BaseHTTPMiddleware`) because `BaseHTTPMiddleware` runs the endpoint in a separate async task. This breaks SQLAlchemy's async session greenlet context, causing `MissingGreenlet` errors. Pure ASGI keeps everything in the same async context.

## Implementation

**File:** `app/api/v1/auth/refresh_middleware.py`

```python
class TokenRefreshMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...
```

## Paths That Skip Token Refresh

```python
SKIP_PREFIXES = (
    "/api/v1/auth/",    # auth endpoints issue tokens — don't refresh
    "/health",          # public health check
    "/docs",            # Swagger UI
    "/redoc",           # ReDoc
    "/openapi.json",    # OpenAPI spec
)
```

Also skips the root path `/`.

## Full Flow

### Case 1: Valid Access Token

```
1. Extract access token from Authorization header or cookie
2. pyjwt.decode(access_token) → success, type="access"
3. Pass through unchanged: await self.app(scope, receive, send)
```

No modification to request or response. Fastest path.

### Case 2: Expired Access Token, Valid Refresh Token

```
1. Extract access token → pyjwt.decode() → ExpiredSignatureError → caught
2. Extract refresh token from X-Refresh-Token header or cookie
3. decode_refresh_token(refresh_token) → valid
4. create_access_token() from refresh token claims → new token (30 min)
5. Replace Authorization header in scope["headers"] with new token
6. Wrap send() to add X-New-Access-Token response header
7. Call inner app with modified scope and wrapped send
```

The JWT Guard downstream sees the new valid token. The frontend receives the new token in `X-New-Access-Token` and updates its cookie.

### Case 3: Both Tokens Expired/Invalid

```
1. Access token → ExpiredSignatureError → caught
2. Refresh token → ExpiredSignatureError → caught
3. new_access_token = None
4. Pass through unchanged: await self.app(scope, receive, send)
```

The middleware does nothing. The JWT Guard will raise 401.

### Case 4: No Tokens at All

```
1. No Authorization header, no cookie → access_token = None
2. No X-Refresh-Token header, no cookie → refresh_token = None
3. Pass through unchanged
```

Same as Case 3 — the JWT Guard handles rejection.

## Token Extraction

The middleware extracts tokens from two sources, with headers taking priority:

### Access Token
1. `Authorization: Bearer <token>` header → strips "Bearer " prefix
2. `grapoll-access-token` or `__Secure-grapoll-access-token` cookie

### Refresh Token
1. `X-Refresh-Token: <token>` header
2. `grapoll-refresh-token` or `__Secure-grapoll-refresh-token` cookie

## Request Modification: `_replace_auth_header`

```python
def _replace_auth_header(self, headers, new_token):
    # Remove old Authorization header
    new_headers = [(k, v) for k, v in headers if k.lower() != b"authorization"]
    # Add new one
    new_headers.append((b"authorization", f"Bearer {new_token}".encode()))
    return new_headers
```

This modifies `scope["headers"]` — the raw ASGI header list. When the request reaches the JWT Guard, it reads this modified header and sees a valid token.

## Response Modification: `send_with_token`

```python
async def send_with_token(message: Message) -> None:
    if message["type"] == "http.response.start":
        headers = list(message.get("headers", []))
        headers.append((b"x-new-access-token", token_to_inject.encode()))
        message["headers"] = headers
    await send(message)
```

The `send` function is called twice by the inner app:
1. `http.response.start` — status code + headers → this is where we inject `X-New-Access-Token`
2. `http.response.body` — response body → passed through unchanged

## Position in Middleware Stack

Registered second (innermost after CORS):

```python
# main.py
app.add_middleware(CORSMiddleware, ...)      # ① inner
app.add_middleware(TokenRefreshMiddleware)    # ②
app.add_middleware(SlowAPIMiddleware)         # ③ outer
```

Execution order:
```
Request → SlowAPI → [TokenRefresh] → CORS → Router
Response ← SlowAPI ← [TokenRefresh] ← CORS ← Router
```

Runs **after** rate limiting (so rate-limited requests are rejected before token processing) and **before** CORS (so the refreshed token header is added before CORS processes the response).

## Key Design Decision: Middleware Does Not Enforce Auth

The middleware **never** returns 401. It only attempts to refresh tokens. If it can't, it passes the request through unchanged. This is because the middleware doesn't know whether the target endpoint requires authentication (`CurrentUser`), allows anonymous access (`CurrentUserOptional`), or is fully public (no dependency).

The JWT Guard (`get_current_user` / `get_current_user_optional`) is the one that decides whether to reject or allow.

## Related Files

| File | Role |
|------|------|
| `app/api/v1/auth/refresh_middleware.py` | This middleware |
| `app/api/v1/auth/jwt.py` | `create_access_token()`, `decode_refresh_token()` |
| `app/api/v1/auth/jwt_guard.py` | JWT Guard that validates the (potentially refreshed) token |
| `app/core/config.py` | `JWT_SECRET`, `JWT_ALGORITHM` |
| `app/main.py` | Middleware registration (line 64) |
| **Frontend** | |
| `lib/auth/tokens.ts` | `handleTokenRefreshResponse()` — reads `X-New-Access-Token` and updates cookie |
| `config/openapi-runtime.ts` | Calls `handleTokenRefreshResponse()` after every fetch |
