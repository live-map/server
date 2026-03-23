# Full Flow of Middleware and Interceptor in Grapoll

## Overview

Every HTTP request to FastAPI passes through two layers of processing before reaching the endpoint:

1. **Middleware** (ASGI layer) — global, runs on every request
2. **Interceptor** (Depends layer) — per-endpoint, runs only on endpoints that declare it

```
HTTP Request
    │
    ▼
┌─────────────────────────┐
│     Middleware Stack     │  ← Global, every request
│  (ASGI layer)            │
│                          │
│  ④ add_request_id        │
│  ③ SlowAPIMiddleware     │
│  ② TokenRefreshMiddleware│
│  ① CORSMiddleware        │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│     FastAPI Router       │  ← URL matching
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  Interceptor (Depends)   │  ← Per-endpoint
│                          │
│  get_current_user()      │
│  get_current_admin()     │
│  get_post_service()      │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│     Endpoint Function    │  ← Business logic
└──────────────────────────┘
```

---

## What is Middleware?

Middleware is a **wrapper around the entire application**. It sits at the ASGI level — below FastAPI, before any routing or request parsing happens. Every HTTP request passes through all middleware layers, regardless of which endpoint it's heading to.

Middleware has access to:
- Raw request headers (as bytes)
- Request path and method
- The ability to modify the request before FastAPI sees it
- The ability to modify the response after FastAPI generates it
- The ability to short-circuit (return a response without calling the endpoint)

Middleware does **not** have access to:
- Parsed request body
- Path parameters
- Which endpoint will handle the request
- FastAPI's dependency injection system

## What is an Interceptor?

In FastAPI, there's no built-in concept called "interceptor". The equivalent is **dependency injection via `Depends()`**. A dependency function runs before the endpoint, can extract and validate data from the request, and can reject the request by raising `HTTPException`.

The term "interceptor" describes the **pattern** of using `Depends()` to intercept requests before the endpoint processes them — specifically for authentication guards like `CurrentUser`, `CurrentAdmin`.

Interceptor has access to:
- Parsed `Request` object
- Path parameters, query parameters, request body
- FastAPI's dependency injection system
- Other dependencies (chaining)

Interceptor does **not** have access to:
- The response (it runs before the endpoint)
- Other requests (it's scoped to a single request + endpoint)

---

## Middleware Stack in Grapoll

### Registration in `app/main.py`

```python
# main.py
app.add_middleware(CORSMiddleware, ...)      # ① registered first
app.add_middleware(TokenRefreshMiddleware)    # ② registered second
app.add_middleware(SlowAPIMiddleware)         # ③ registered third

@app.middleware("http")                      # ④ registered fourth
async def add_request_id(request, call_next):
```

### How Wrapping Works

Each `add_middleware` wraps the previous layer. The **last registered becomes the outermost layer**:

```python
# What FastAPI builds internally:
layer_0 = FastAPI_Router                          # endpoints
layer_1 = CORSMiddleware(layer_0)                 # wraps router
layer_2 = TokenRefreshMiddleware(layer_1)          # wraps CORS
layer_3 = SlowAPIMiddleware(layer_2)               # wraps TokenRefresh
layer_4 = add_request_id_middleware(layer_3)        # wraps SlowAPI (outermost)
```

### Execution Order

ASGI middleware executes in **reverse registration order** (LIFO — Last In, First Out). The outermost layer runs first on the way in, and last on the way out:

```
Request ──→  ④ add_request_id
             ③ SlowAPIMiddleware
             ② TokenRefreshMiddleware
             ① CORSMiddleware
             FastAPI Router + Depends + Endpoint
Response ←─  ① CORSMiddleware
             ② TokenRefreshMiddleware
             ③ SlowAPIMiddleware
             ④ add_request_id
```

---

## Full Request Flow: Creating a Post with Expired Access Token

### Request

```
POST /api/v1/posts HTTP/1.1
Authorization: Bearer eyJ... (expired)
X-Refresh-Token: eyJ... (valid)
Content-Type: application/json

{ "title": "Best pizza?", "content": "Recommendations?" }
```

### Step 1: Uvicorn

Receives raw TCP bytes, parses HTTP, creates ASGI `scope`:

```python
scope = {
    "type": "http",
    "path": "/api/v1/posts",
    "method": "POST",
    "headers": [
        (b"authorization", b"Bearer eyJ..."),
        (b"x-refresh-token", b"eyJ..."),
        (b"content-type", b"application/json"),
    ],
}
```

### Step 2: ④ add_request_id (outermost middleware)

```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)  # → passes to SlowAPIMiddleware
    response.headers["X-Request-ID"] = request_id
    return response
```

- Generates `X-Request-ID: "550e8400-..."`
- Calls `call_next()` → passes to next layer
- Adds `X-Request-ID` to response on the way back

### Step 3: ③ SlowAPIMiddleware

- Checks rate limit: this IP has 15/60 requests this minute → OK
- Calls inner app → passes to next layer
- If rate limit exceeded → returns 429 immediately, skips all inner layers

### Step 4: ② TokenRefreshMiddleware

This is where the token refresh happens. Detailed flow:

```python
# a. Check if path should skip
path = "/api/v1/posts"  # not in SKIP_PREFIXES → continue

# b. Extract tokens from raw headers
access_token = "eyJ..."   # from Authorization header
refresh_token = "eyJ..."  # from X-Refresh-Token header

# c. Validate access token
pyjwt.decode(access_token, JWT_SECRET, ...)
# → ExpiredSignatureError! Token expired.
# → Caught and swallowed (pass)

# d. Attempt refresh
refresh_payload = decode_refresh_token(refresh_token)
# → Valid! Returns { "sub": "clx7abc123", "email": "kim@gmail.com", ... }

new_access_token = create_access_token(
    user_id=refresh_payload["sub"],
    email=refresh_payload["email"],
    ...
)
# → New token valid for 30 minutes

# e. Inject new token into scope["headers"]
scope["headers"] = self._replace_auth_header(scope["headers"], new_access_token)
# Before: (b"authorization", b"Bearer <expired>")
# After:  (b"authorization", b"Bearer <new_valid>")

# f. Wrap send() to add X-New-Access-Token to response
async def send_with_token(message):
    if message["type"] == "http.response.start":
        headers.append((b"x-new-access-token", new_access_token.encode()))
    await send(message)

await self.app(scope, receive, send_with_token)
```

### Step 5: ① CORSMiddleware

- Checks `Origin` header → matches `http://localhost:3000` → allowed
- Adds `Access-Control-Allow-Origin: http://localhost:3000` to response
- If this were an `OPTIONS` preflight → responds immediately with 200, skips all inner layers

### Step 6: FastAPI Router

- Matches `POST /api/v1/posts` → `create_post()` endpoint
- Begins resolving `Depends()` dependencies

### Step 7: Interceptor — JWT Guard (Depends)

FastAPI sees `current_user: CurrentUser` on the endpoint and resolves the dependency chain:

```python
# CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]

async def get_current_user(request, token_from_header):
    token = token_from_header  # ← the NEW valid token injected by middleware

    payload = decode_token(token)
    # → Valid! { "sub": "clx7abc123", "type": "access", ... }

    return JWTPayload(user_id="clx7abc123", email="kim@gmail.com", ...)
```

### Step 8: Interceptor — Service Injection (Depends)

```python
# service: AuthService = Depends()
# → FastAPI calls AuthService.__init__(db=Depends(get_db))
# → Creates AuthService with AuthRepository
```

### Step 9: Endpoint Execution

```python
async def create_post(data, current_user, postService):
    post = await postService.create_post_without_commit(
        user_id=current_user.user_id,  # "clx7abc123"
        title=data.title,
        content=data.content,
    )
```

### Step 10: Response Travels Back Through Middleware

```
FastAPI Router → JSONResponse(201, { "id": "...", "title": "..." })
    │
    ▼
① CORSMiddleware
    → adds: Access-Control-Allow-Origin: http://localhost:3000
    │
    ▼
② send_with_token (wrapped by TokenRefreshMiddleware)
    → adds: X-New-Access-Token: eyJ... (the new access token)
    │
    ▼
③ SlowAPIMiddleware
    → pass through
    │
    ▼
④ add_request_id
    → adds: X-Request-ID: 550e8400-...
    │
    ▼
Uvicorn → TCP bytes
```

### Final Response

```
HTTP/1.1 201 Created
Access-Control-Allow-Origin: http://localhost:3000
X-New-Access-Token: eyJhbGciOiJIUzI1NiJ9...
X-Request-ID: 550e8400-...
Content-Type: application/json

{
  "id": "clx9xyz789",
  "title": "Best pizza?",
  "content": "Recommendations?",
  "authorId": "clx7abc123"
}
```

---

## Failure Case: Both Tokens Expired

If both access and refresh tokens are expired:

```
② TokenRefreshMiddleware
    → access token: ExpiredSignatureError → caught, swallowed
    → refresh token: ExpiredSignatureError → caught, swallowed
    → new_access_token = None
    → passes request through UNCHANGED (original expired token still in headers)

FastAPI Router → resolves Depends(get_current_user)

JWT Guard (get_current_user):
    → decode_token(expired_token) → ExpiredSignatureError
    → raises HTTPException(401, "Token has expired. Please refresh your token.")

FastAPI's built-in exception handler:
    → converts HTTPException → JSONResponse(401)

Response travels back through middleware stack:
    ② TokenRefreshMiddleware → send() was NOT wrapped (no new token)
    → 401 response passes through unchanged
```

The middleware **never rejects** requests. It only refreshes when possible. The JWT Guard is the one that enforces auth and returns 401.

---

## Why This Separation?

| Responsibility | Middleware | Interceptor (Depends) |
|---|---|---|
| Token refresh | TokenRefreshMiddleware | |
| CORS headers | CORSMiddleware | |
| Rate limiting | SlowAPIMiddleware | |
| Request ID | add_request_id | |
| Auth enforcement | | CurrentUser (required) |
| Optional auth | | CurrentUserOptional |
| Admin check | | CurrentAdmin |
| DB session | | Depends(get_db) |
| Service injection | | Depends(AuthService) |

Middleware handles **cross-cutting concerns** (things that apply to every request regardless of endpoint). Interceptors handle **per-endpoint decisions** (things that vary by endpoint — like whether auth is required, optional, or admin-only).

The middleware doesn't know which endpoints require auth. It only knows how to refresh tokens. The interceptor (JWT Guard) knows whether **this specific endpoint** requires auth, and enforces it accordingly.
