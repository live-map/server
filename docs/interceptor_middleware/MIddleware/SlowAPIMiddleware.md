# SlowAPIMiddleware

## What It Does

Rate limits API requests to prevent abuse. Limits each IP address to **60 requests per minute** by default. Returns `429 Too Many Requests` when the limit is exceeded.

## Configuration in Grapoll

```python
# app/main.py
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Create limiter with default rate
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# Attach to app state (SlowAPIMiddleware reads from app.state.limiter)
app.state.limiter = limiter

# Register middleware
app.add_middleware(SlowAPIMiddleware)
```

## How It Works

### Normal Request (Under Limit)

```
Request arrives from IP 192.168.1.100
    → SlowAPIMiddleware checks: this IP has 15 requests this minute
    → 15 < 60 → OK, increment counter
    → Pass to inner app
```

### Rate Limited Request

```
Request arrives from IP 192.168.1.100
    → SlowAPIMiddleware checks: this IP has 60 requests this minute
    → 60 >= 60 → LIMIT EXCEEDED
    → Raises RateLimitExceeded exception
    → Exception handler returns 429:

HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{"detail": "Too many requests. Please try again later."}
```

The request never reaches TokenRefreshMiddleware, CORSMiddleware, or the endpoint.

## Exception Handler

```python
# app/main.py
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )
```

## Per-Endpoint Rate Limits

The default `60/minute` applies globally, but individual endpoints can override:

```python
@app.get("/expensive")
@limiter.limit("5/minute")
async def expensive_operation(request: Request):
    ...
```

## Key Function: `get_remote_address`

```python
key_func=get_remote_address
```

This determines **what to rate limit by**. `get_remote_address` extracts the client's IP from the request. Behind a reverse proxy (nginx), you'd use `X-Forwarded-For` instead.

## Position in Middleware Stack

Registered third (outermost before `add_request_id`):

```python
app.add_middleware(CORSMiddleware, ...)      # ① inner
app.add_middleware(TokenRefreshMiddleware)    # ②
app.add_middleware(SlowAPIMiddleware)         # ③ outer
```

Execution order:
```
Request → [SlowAPI] → TokenRefresh → CORS → Router
```

Runs **before** token refresh — so rate-limited requests are rejected immediately without wasting CPU on JWT decoding.

## Related Files

| File | Role |
|------|------|
| `app/main.py` | Limiter creation (line 30), middleware registration (line 67), exception handler (line 80) |

## Library

[SlowAPI](https://github.com/laurentS/slowapi) — a rate limiting library for Starlette/FastAPI, based on Flask-Limiter.
