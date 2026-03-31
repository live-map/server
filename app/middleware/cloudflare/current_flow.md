# CloudflareProMiddleware - Current Flow

## What It Does

Blocks vote requests (`POST /api/v1/polls/{uuid}/vote`) from outside South Korea using the `CF-IPCountry` header injected by Cloudflare.

## Protected Endpoint

Only this exact pattern is blocked:

```
POST /api/v1/polls/{uuid}/vote
```

Regex: `^/api/v1/polls/[0-9a-f-]{36}/vote$`

All other endpoints pass through freely.

## Request Flow

```
Incoming Request
│
├── Not HTTP (WebSocket, lifespan)?
│   └── Pass through
│
├── Not POST /api/v1/polls/{uuid}/vote?
│   └── Pass through
│
├── CF-IPCountry header missing?
│   └── 403 { code: "GEO_MISSING" }
│
├── Country is KR?
│   └── Pass through
│
└── Country is not KR
    └── 403 { code: "GEO_BLOCKED" }
```

## 403 Responses

**Missing header** (direct server access or Cloudflare misconfigured):
```json
{
  "detail": "Unable to verify request origin.",
  "code": "GEO_MISSING"
}
```

**Blocked country**:
```json
{
  "detail": "Access restricted to South Korea.",
  "code": "GEO_BLOCKED",
  "country": "US"
}
```

## Middleware Execution Order (main.py)

```
Request → CloudflareProMiddleware → TokenRefreshMiddleware → SlowAPI → Route Handler
```

CloudflareProMiddleware runs first. Blocked requests never reach token refresh or rate limiting.

## File Location

```
server/app/middleware/cloudflare_pro.py
```

Registered in `main.py`:
```python
app.add_middleware(CloudflareProMiddleware)
```

No config or environment variables needed. Allowed countries default to `{"KR"}`.

## To Disable

Remove the `app.add_middleware(CloudflareProMiddleware)` line from `main.py`.

## Limitations (Free/Pro Tier)

- Cannot detect VPN users with Korean exit IPs (CF-IPCountry will say "KR")
- No bot management scoring (Enterprise only)
- No managed VPN/proxy IP list (Enterprise only)
- `cf.threat_score` is deprecated (always returns 0)

VPN detection would require application-level solutions (phone verification, Kakao-only auth, third-party IP intelligence API).
