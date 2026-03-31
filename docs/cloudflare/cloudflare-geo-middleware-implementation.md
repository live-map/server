# Cloudflare Geo Middleware Implementation (Free/Pro Plan)

> **Middleware:** `CloudflareGeoMiddleware`
> **File:** `server/app/middleware/cloudflare_geo.py`
> **Cloudflare Plan Required:** Free or Pro (works on all tiers)
> **Purpose:** Block non-Korean users from voting on polls

---

## What This Middleware Does

```
[User's Browser]
       |
       ↓ HTTPS request
[Cloudflare Edge]
  • Looks up visitor's IP in geo database
  • Injects CF-IPCountry, CF-Connecting-IP, location headers
       |
       ↓ HTTPS + injected headers
[FastAPI: CloudflareGeoMiddleware]
  • Reads CF-IPCountry
  • If vote request + country != KR → 403 Forbidden
  • If vote request + country == KR → pass through
  • If non-vote request → always pass through (stores geo data only)
       |
       ↓
[Vote Handler]
```

---

## Headers Consumed by This Middleware

### Core Headers (Auto-injected by Cloudflare on ALL plans)

| Header | Example | Description | Required Setup |
|--------|---------|-------------|----------------|
| `CF-IPCountry` | `KR` | ISO 3166-1 alpha-2 country code | Toggle ON: Dashboard → Network → IP Geolocation |
| `CF-Connecting-IP` | `203.0.113.45` | Visitor's real IP (bypasses proxies/load balancers) | Automatic (always present) |
| `CF-Ray` | `8f3a2b1c0d4e5f6a-NRT` | Request trace ID + data center code | Automatic |
| `CF-Visitor` | `{"scheme":"https"}` | Connection scheme | Automatic |
| `X-Forwarded-For` | `203.0.113.45, 172.68.0.1` | IP chain (client → Cloudflare) | Automatic |
| `X-Forwarded-Proto` | `https` | Protocol used by visitor | Automatic |

### Location Headers (Managed Transform — Free+, must enable)

These provide detailed geo data. Enable in Dashboard → Rules → Transform Rules → Managed Transforms → "Add visitor location headers".

| Header | Example | Description |
|--------|---------|-------------|
| `cf-ipcity` | `Seoul` | City name |
| `cf-ipcontinent` | `AS` | Continent code (AF, AN, AS, EU, NA, OC, SA) |
| `cf-iplatitude` | `37.5665` | Approximate latitude |
| `cf-iplongitude` | `126.9780` | Approximate longitude |
| `cf-region` | `Seoul` | Region/province name |
| `cf-region-code` | `11` | Region code |
| `cf-postal-code` | `04524` | Postal code |
| `cf-timezone` | `Asia/Seoul` | IANA timezone identifier |
| `cf-metro-code` | `0` | Metro area code (mainly US) |

---

## HTTPS Request Examples

### Example 1: Korean User in Seoul Votes (ALLOWED)

```http
POST /api/v1/polls/550e8400-e29b-41d4-a716-446655440000/vote HTTP/1.1
Host: api.grapoll.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ── Cloudflare Auto-Injected Headers ─────────────────────────
CF-Connecting-IP: 203.0.113.45
CF-IPCountry: KR
CF-Ray: 8f3a2b1c0d4e5f6a-NRT
CF-Visitor: {"scheme":"https"}
X-Forwarded-For: 203.0.113.45
X-Forwarded-Proto: https

# ── Managed Transform: Visitor Location Headers ──────────────
cf-ipcity: Seoul
cf-ipcontinent: AS
cf-iplatitude: 37.5665
cf-iplongitude: 126.9780
cf-region: Seoul
cf-region-code: 11
cf-postal-code: 04524
cf-timezone: Asia/Seoul
cf-metro-code: 0

{"interaction_type": "BINARY", "option_id": "opt-yes-uuid"}
```

**Middleware decision:**
```
CF-IPCountry = "KR"
"KR" in allowed_countries {"KR"} → ✅ PASS THROUGH
```

**Response:** Vote handler processes normally → `200 OK`

---

### Example 2: American User in New York Votes (BLOCKED)

```http
POST /api/v1/polls/550e8400-e29b-41d4-a716-446655440000/vote HTTP/1.1
Host: api.grapoll.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ── Cloudflare Auto-Injected Headers ─────────────────────────
CF-Connecting-IP: 198.51.100.22
CF-IPCountry: US
CF-Ray: 7e2b4a9c1d3f5e8b-EWR
CF-Visitor: {"scheme":"https"}
X-Forwarded-For: 198.51.100.22
X-Forwarded-Proto: https

# ── Managed Transform: Visitor Location Headers ──────────────
cf-ipcity: New York
cf-ipcontinent: NA
cf-iplatitude: 40.7128
cf-iplongitude: -74.0060
cf-region: New York
cf-region-code: NY
cf-postal-code: 10001
cf-timezone: America/New_York
cf-metro-code: 501

{"interaction_type": "BINARY", "option_id": "opt-yes-uuid"}
```

**Middleware decision:**
```
CF-IPCountry = "US"
"US" NOT in allowed_countries {"KR"} → ❌ BLOCKED
```

**Response:**
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "detail": "Access restricted to South Korea.",
  "code": "GEO_BLOCKED",
  "country": "US"
}
```

---

### Example 3: Japanese User in Tokyo Votes (BLOCKED)

```http
POST /api/v1/polls/550e8400-e29b-41d4-a716-446655440000/vote HTTP/1.1
Host: api.grapoll.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

CF-Connecting-IP: 192.0.2.88
CF-IPCountry: JP
CF-Ray: 9a1c3d5e7f8b0c2d-NRT
cf-ipcity: Tokyo
cf-ipcontinent: AS
cf-timezone: Asia/Tokyo
```

**Middleware decision:**
```
CF-IPCountry = "JP"
"JP" NOT in allowed_countries {"KR"} → ❌ BLOCKED
```

**Response:**
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "detail": "Access restricted to South Korea.",
  "code": "GEO_BLOCKED",
  "country": "JP"
}
```

---

### Example 4: US User Browses Polls (ALLOWED — not a vote request)

```http
GET /api/v1/polls?sort=popular&limit=20 HTTP/1.1
Host: api.grapoll.com

CF-Connecting-IP: 198.51.100.22
CF-IPCountry: US
CF-Ray: 7e2b4a9c1d3f5e8b-EWR
cf-ipcity: New York
```

**Middleware decision:**
```
Method = GET, Path = /api/v1/polls
NOT a vote request (POST /api/v1/polls/{id}/vote)
→ ✅ PASS THROUGH (geo data stored in request.state.cf_geo for logging)
```

**Response:** Poll list returned normally → `200 OK`

---

### Example 5: VPN User (Korean Server) Votes — FREE/PRO LIMITATION

```http
POST /api/v1/polls/550e8400-e29b-41d4-a716-446655440000/vote HTTP/1.1
Host: api.grapoll.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# NordVPN Korean exit node — Cloudflare sees Korean IP
CF-Connecting-IP: 112.175.88.12
CF-IPCountry: KR
CF-Ray: 5d4c3b2a1e0f9g8h-NRT
cf-ipcity: Seoul
cf-timezone: Asia/Seoul
```

**Middleware decision:**
```
CF-IPCountry = "KR"
"KR" in allowed_countries {"KR"} → ✅ PASS THROUGH

⚠️ VPN user BYPASSES geo-blocking!
Free/Pro plan cannot distinguish VPN Korean IP from real Korean IP.
```

**This is the limitation of Free/Pro.** Enterprise plan with WAF Managed IP Lists solves this — see Enterprise middleware documentation.

---

### Example 6: Local Development (No Cloudflare)

```http
POST /api/v1/polls/550e8400-e29b-41d4-a716-446655440000/vote HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# No CF-* headers (direct origin access, no Cloudflare proxy)

{"interaction_type": "BINARY", "option_id": "opt-yes-uuid"}
```

**Scenario A:** `CLOUDFLARE_ENABLED=false` (default)
```
Middleware is disabled → ✅ PASS THROUGH immediately (zero overhead)
```

**Scenario B:** `CLOUDFLARE_ENABLED=true` but no CF headers
```
CF-IPCountry = None (header missing)
Vote request detected, but no country header → log warning, ✅ PASS THROUGH
(Doesn't break local dev — just warns that Cloudflare isn't proxying)
```

---

## Middleware Architecture

### Pattern: Pure ASGI Middleware

We use the same pattern as the existing `TokenRefreshMiddleware` (`app/api/v1/auth/refresh_middleware.py`) — raw ASGI instead of Starlette's `BaseHTTPMiddleware`. This prevents breaking SQLAlchemy's async greenlet context.

```python
class CloudflareGeoMiddleware:
    """Pure ASGI middleware — no BaseHTTPMiddleware."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # ... middleware logic ...
```

### Class Structure

```
CloudflareGeoMiddleware
├── __init__(app)
│   └── Parse settings: enabled, allowed_countries set
│
├── __call__(scope, receive, send)            # Main entry point
│   ├── Skip non-HTTP requests
│   ├── Skip if CLOUDFLARE_ENABLED=false
│   ├── _parse_headers(scope)                 # Raw ASGI headers → dict
│   ├── _extract_geo_data(headers)            # CF headers → geo dict
│   ├── Store geo_data in scope["state"]["cf_geo"]
│   ├── _is_vote_request(method, path)        # Regex match
│   │   ├── Not vote → pass through
│   │   └── Vote request:
│   │       ├── No CF-IPCountry → warn + pass through
│   │       ├── Country in allowed → pass through
│   │       └── Country NOT allowed → _send_403()
│   └── Pass through or block
│
├── _parse_headers(scope) → dict[str, str]
│   └── Decode ASGI raw headers (bytes) to lowercase string dict
│
├── _extract_geo_data(headers) → dict
│   └── Map CF header names to structured geo dict:
│       {country, ip, ray, city, continent, latitude, longitude,
│        region, region_code, postal_code, timezone, metro_code}
│
├── _is_vote_request(method, path) → bool
│   └── Regex: POST /api/v1/polls/{uuid}/vote
│
└── _send_403(send, detail, code, extra) → None
    └── Send 403 JSON response via raw ASGI send()
```

### Data Flow: `scope["state"]` → `request.state`

Starlette/FastAPI reads `request.state` from `scope["state"]`. When the middleware writes:

```python
scope["state"]["cf_geo"] = {
    "country": "KR",
    "ip": "203.0.113.45",
    "city": "Seoul",
    ...
}
```

Downstream in the vote controller, it's accessible as:

```python
# In cast_vote() endpoint handler:
request.state.cf_geo
# → {"country": "KR", "ip": "203.0.113.45", "city": "Seoul", ...}

request.state.cf_geo.get("ip")
# → "203.0.113.45"
```

### Vote Controller IP Update

**Current** (`app/api/v1/poll/controller.py`, line 486–491):
```python
voter_ip = (
    request.headers.get("fly-client-ip")
    or (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or None)
    or (request.client.host if request.client else None)
)
```

**Updated** — prefer Cloudflare's authoritative IP:
```python
cf_geo = getattr(request.state, "cf_geo", None)
voter_ip = (
    (cf_geo.get("ip") if cf_geo else None)            # CF-Connecting-IP (most reliable)
    or request.headers.get("fly-client-ip")            # Fly.io header (fallback)
    or (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or None)
    or (request.client.host if request.client else None)
)
```

---

## Middleware Registration Order

In `app/main.py`, Starlette middleware wraps in reverse — last `add_middleware` call runs first (outermost):

```python
# Registration order:
app.add_middleware(CORSMiddleware, ...)              # innermost
app.add_middleware(CloudflareEnterpriseMiddleware)    # Enterprise checks (later plan)
app.add_middleware(CloudflareGeoMiddleware)           # Geo check
app.add_middleware(TokenRefreshMiddleware)            # JWT refresh
app.add_middleware(SlowAPIMiddleware)                 # Rate limit (outermost)
```

**Actual execution order (outermost → innermost):**
```
Request
  ↓ SlowAPIMiddleware          — Rate limit (drop abusive IPs early)
  ↓ TokenRefreshMiddleware     — Auto-refresh JWT before auth checks
  ↓ CloudflareGeoMiddleware    — Country check (cheapest — single header compare)
  ↓ CloudflareEnterpriseMiddleware — VPN/bot check (catches VPN bypass)
  ↓ CORSMiddleware             — CORS headers
  ↓ Router → Endpoint Handler
```

Geo runs before Enterprise because:
1. It's the cheapest check (single string comparison)
2. It blocks the most traffic (all non-KR countries)
3. Enterprise only needs to check the VPN users who passed geo-blocking

---

## Configuration

### Settings Added to `app/core/config.py`

```python
# Cloudflare Free/Pro
CLOUDFLARE_ENABLED: bool = False              # Master toggle
CLOUDFLARE_ALLOWED_COUNTRIES: str = "KR"      # Comma-separated ISO codes
```

### `.env` File

```env
# Cloudflare Integration
CLOUDFLARE_ENABLED=false
CLOUDFLARE_ALLOWED_COUNTRIES=KR
```

### Cloudflare Dashboard Setup

1. **Enable IP Geolocation:**
   Dashboard → Network → IP Geolocation → **ON**
   (This enables the `CF-IPCountry` header)

2. **Enable Visitor Location Headers (optional but recommended):**
   Dashboard → Rules → Transform Rules → Managed Transforms → "Add visitor location headers" → **ON**
   (This enables `cf-ipcity`, `cf-iplatitude`, `cf-timezone`, etc.)

3. **Ensure orange cloud (proxy) is active:**
   Dashboard → DNS → your A/CNAME record must have the orange cloud icon (Proxied)
   (If grey cloud / DNS only, Cloudflare won't inject any headers)

---

## Limitation of Free/Pro Plan

| Threat | Detected? | Why |
|--------|-----------|-----|
| Foreign user with real foreign IP | ✅ Yes | `CF-IPCountry != KR` |
| Foreign user on Korean VPN (NordVPN, ExpressVPN, etc.) | ❌ No | VPN exit node has Korean IP → `CF-IPCountry = KR` |
| Bot/script from Korean IP | ❌ No | No bot detection on Free/Pro |
| Tor exit node in Korea | ❌ No | Tor exit appears as regular Korean IP |

**Solution:** Enterprise plan with WAF Managed IP Lists detects VPN/proxy/Tor traffic. See Enterprise middleware documentation.

---

## `cf_geo` Data Shape Reference

```python
request.state.cf_geo = {
    # Core (always present if Cloudflare is proxying)
    "country": "KR",                  # str | None — CF-IPCountry
    "ip": "203.0.113.45",            # str | None — CF-Connecting-IP
    "ray": "8f3a2b1c0d4e5f6a-NRT",  # str | None — CF-Ray

    # Location (present if Managed Transform enabled)
    "city": "Seoul",                  # str | None — cf-ipcity
    "continent": "AS",                # str | None — cf-ipcontinent
    "latitude": "37.5665",            # str | None — cf-iplatitude
    "longitude": "126.9780",          # str | None — cf-iplongitude
    "region": "Seoul",                # str | None — cf-region
    "region_code": "11",              # str | None — cf-region-code
    "postal_code": "04524",           # str | None — cf-postal-code
    "timezone": "Asia/Seoul",         # str | None — cf-timezone
    "metro_code": "0",                # str | None — cf-metro-code
}
```
