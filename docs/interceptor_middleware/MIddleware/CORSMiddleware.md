# CORSMiddleware

## What It Does

CORS (Cross-Origin Resource Sharing) controls which websites can make requests to your API. Without it, browsers block requests from `localhost:3000` (Next.js) to `localhost:8000` (FastAPI) because they're different origins.

## Configuration in Grapoll

```python
# app/main.py
_cors_origins = [str(settings.FRONTEND_URL).rstrip("/")]
if settings.DEBUG:
    _cors_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie", "X-Refresh-Token"],
    expose_headers=["X-New-Access-Token"],
)
```

## What Each Parameter Does

| Parameter | Value | Purpose |
|---|---|---|
| `allow_origins` | `["http://localhost:3000"]` | Only requests from these origins are allowed |
| `allow_credentials` | `True` | Allow cookies and Authorization headers in cross-origin requests |
| `allow_methods` | `["GET", "POST", ...]` | HTTP methods the frontend can use |
| `allow_headers` | `["Content-Type", "Authorization", "X-Refresh-Token"]` | Headers the frontend can send |
| `expose_headers` | `["X-New-Access-Token"]` | Headers the frontend can read from the response |

## How It Processes Requests

### Simple Request (GET, POST with standard headers)

```
Browser sends:
    GET /api/v1/polls
    Origin: http://localhost:3000

CORSMiddleware:
    1. Checks Origin against allow_origins → matches
    2. Passes request to inner app
    3. Adds to response:
       Access-Control-Allow-Origin: http://localhost:3000
       Access-Control-Allow-Credentials: true
```

### Preflight Request (OPTIONS)

Before sending requests with custom headers (like `Authorization`, `X-Refresh-Token`), the browser sends a preflight:

```
Browser sends:
    OPTIONS /api/v1/posts
    Origin: http://localhost:3000
    Access-Control-Request-Method: POST
    Access-Control-Request-Headers: Authorization, X-Refresh-Token

CORSMiddleware:
    1. Sees OPTIONS with CORS headers → this is a preflight
    2. Checks Origin → matches
    3. Returns 200 immediately (does NOT call inner app):
       Access-Control-Allow-Origin: http://localhost:3000
       Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
       Access-Control-Allow-Headers: Content-Type, Authorization, Cookie, X-Refresh-Token
       Access-Control-Allow-Credentials: true
       Access-Control-Max-Age: 600  (cache preflight for 10 minutes)

Browser:
    Preflight passed → now sends the actual POST request
```

### Why `expose_headers` Matters

By default, browsers can only read a few standard response headers (`Content-Type`, `Content-Length`, etc.). Custom headers like `X-New-Access-Token` are hidden unless explicitly exposed:

```python
expose_headers=["X-New-Access-Token"]
```

Without this, the frontend's `handleTokenRefreshResponse()` would never see the new access token from the TokenRefreshMiddleware.

## Position in Middleware Stack

CORSMiddleware is registered **first** (innermost), meaning it runs **last** among middleware on incoming requests. This is correct because:
- On **preflight** (OPTIONS) → it short-circuits before any other middleware processes the request
- On **normal requests** → it adds CORS headers to the response on the way back, after all other middleware have added their headers

```
Request → add_request_id → SlowAPI → TokenRefresh → [CORS] → Router
Response ← add_request_id ← SlowAPI ← TokenRefresh ← [CORS] ← Router
```

## Source

`fastapi.middleware.cors.CORSMiddleware` (re-exported from Starlette)

**File:** `app/main.py` lines 53-60
