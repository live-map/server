# How Cloudflare Works

## What Cloudflare Is

Cloudflare is a **reverse proxy** that sits between users and your server. When someone visits `grapoll.kr`, they connect to Cloudflare first — not your server. Cloudflare inspects the request, applies security rules, checks its cache, and then forwards the request to your actual server.

Your server's real IP is hidden. Users only see Cloudflare's IP.

---

## How DNS Changes With Cloudflare

### Without Cloudflare

```
Browser: "What's the IP of grapoll.kr?"
DNS:     "It's 149.248.xx.xx" (your server's real IP)
Browser: → connects directly to your server
```

### With Cloudflare

```
Browser: "What's the IP of grapoll.kr?"
DNS:     "It's 104.21.xx.xx" (Cloudflare's IP)
Browser: → connects to Cloudflare
Cloudflare: → forwards to your server (real IP hidden)
```

This happens because you point your domain's **nameservers** to Cloudflare. Cloudflare then controls all DNS responses for your domain and returns its own IPs instead of your server's.

---

## Full Request Flow

```
1. User types grapoll.kr in browser

2. Browser asks DNS: "What's the IP of grapoll.kr?"
       │
       ▼
3. DNS responds with Cloudflare's IP (not your server's IP)
       │
       ▼
4. Browser sends HTTPS request to Cloudflare's IP
       │
       ▼
5. Cloudflare receives the request
       │
       ├── DDoS check: is this a bot/attack? → block if yes
       ├── WAF rules: is this a known exploit pattern? → block if yes
       ├── Cache check: do I have a cached copy? → return immediately if yes
       ├── Record metadata: client IP, country, ray ID
       │
       ▼
6. Cloudflare forwards the request to your actual server (Fly.io)
   with extra headers attached (CF-Connecting-IP, CF-IPCountry, etc.)
       │
       ▼
7. Your server (FastAPI) processes it normally and returns a response
       │
       ▼
8. Cloudflare receives the response from your server
       │
       ├── Cache it if cacheable (static assets, images)
       ├── Compress it (Brotli/gzip)
       │
       ▼
9. Cloudflare sends the response back to the user's browser
```

---

## What Cloudflare Adds to Your Request

Cloudflare doesn't change your request — it **adds extra HTTP headers** before forwarding:

```
Original request from browser:
    GET /api/v1/polls
    Authorization: Bearer eyJ...
    Cookie: grapoll-access-token=eyJ...

After Cloudflare (same request, extra headers):
    GET /api/v1/polls
    Authorization: Bearer eyJ...
    Cookie: grapoll-access-token=eyJ...
    CF-Connecting-IP: 203.0.113.45        ← real client IP
    CF-Ray: 7a1b2c3d4e5f6g7h             ← unique request ID
    X-Forwarded-For: 203.0.113.45         ← standard proxy header
    CF-IPCountry: KR                      ← client's country code
```

Your FastAPI endpoints receive the same `Request` object as before. The Cloudflare headers are just extra headers in `request.headers` — you don't need new dependencies or parameters to access them.

---

## What Cloudflare Provides

### 1. DDoS Protection

Cloudflare absorbs attack traffic before it reaches your server. Since attackers only see Cloudflare's IP (not your server's), they can't bypass it.

### 2. CDN (Content Delivery Network)

Cloudflare has servers in 300+ cities worldwide. Static assets (JS, CSS, images) are cached at the nearest server to the user, so they load faster.

```
Without CDN:
    User in Seoul → request travels to Tokyo (Fly.io) → response

With Cloudflare CDN:
    User in Seoul → Cloudflare Seoul (cached) → response instantly
    (only the first request goes to Tokyo; subsequent requests are served from cache)
```

### 3. Free SSL/TLS

Cloudflare provides HTTPS automatically. It handles certificate generation and renewal.

### 4. WAF (Web Application Firewall)

Blocks common attack patterns: SQL injection, XSS, path traversal, etc.

### 5. Analytics

Dashboard showing traffic volume, countries, threats blocked, cache hit rate, etc.

---

## SSL/TLS Modes

Cloudflare offers four encryption modes between itself and your server:

```
                    Browser ←→ Cloudflare     Cloudflare ←→ Your Server
                    ─────────────────────     ──────────────────────────
Off                 HTTP                      HTTP
Flexible            HTTPS                     HTTP
Full                HTTPS                     HTTPS (any certificate)
Full (Strict)       HTTPS                     HTTPS (valid certificate)
```

### Recommended: Full (Strict)

Since Fly.io provides valid TLS certificates for your app, use **Full (Strict)** for end-to-end encryption:

```
Browser → HTTPS → Cloudflare → HTTPS → Fly.io → FastAPI
```

---

## Caching Rules

Not all requests should be cached. API responses are dynamic and must reach your server every time.

| Path | Action | Why |
|------|--------|-----|
| `api.grapoll.kr/api/*` | Bypass cache | Dynamic API responses |
| `api.grapoll.kr/docs` | Cache 1 hour | Swagger UI is static |
| `grapoll.kr/_next/static/*` | Cache 1 year | Next.js immutable assets (hash in filename) |
| `grapoll.kr/` | Bypass cache | SSR pages are dynamic |

These are configured in the Cloudflare dashboard under **Caching > Cache Rules**.

---

## Impact on Grapoll's Middleware Stack

Cloudflare is transparent to your application. The middleware stack works identically:

```
Without Cloudflare:
    Browser → Fly.io → SlowAPI → TokenRefresh → CORS → Router

With Cloudflare:
    Browser → Cloudflare → Fly.io → SlowAPI → TokenRefresh → CORS → Router
```

### One Code Change: SlowAPI Rate Limiter

When Cloudflare proxies requests, `request.client.host` returns Cloudflare's IP instead of the real user's IP. The rate limiter needs to read the real IP from `CF-Connecting-IP`:

```python
# app/main.py

# Before Cloudflare
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# After Cloudflare
def get_real_ip(request: Request) -> str:
    return request.headers.get("CF-Connecting-IP", request.client.host)

limiter = Limiter(key_func=get_real_ip, default_limits=["60/minute"])
```

The fallback `request.client.host` ensures it works in local development where `CF-Connecting-IP` doesn't exist.

No other code changes are needed. Endpoints, middleware, and interceptors all work the same.

---

## Cloudflare Does NOT Affect Local Development

Cloudflare only applies to production domains. Local development is unchanged:

```
Development (your machine):
    Browser → localhost:3000 (Next.js)
            → localhost:8000 (FastAPI)
    No Cloudflare. No DNS. No domain.

Production (with Cloudflare):
    Browser → grapoll.kr → Cloudflare → your frontend host
            → api.grapoll.kr → Cloudflare → Fly.io (Tokyo)
```

Your `.env` files stay the same. There's nothing to configure locally.

---

## How to Set Up Cloudflare for Grapoll

### Step 1: Create Account & Add Domain

1. Create account at [dash.cloudflare.com](https://dash.cloudflare.com)
2. Add `grapoll.kr`
3. Cloudflare scans existing DNS records

### Step 2: Update Nameservers

Change your domain registrar's nameservers to the ones Cloudflare provides (e.g., `anna.ns.cloudflare.com`, `bob.ns.cloudflare.com`).

### Step 3: Configure DNS Records

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A/CNAME | `@` | your frontend host | Proxied (orange cloud) |
| CNAME | `api` | `grapoll-api.fly.dev` | Proxied (orange cloud) |

### Step 4: Set SSL Mode

Set to **Full (Strict)** in SSL/TLS settings.

### Step 5: Update SlowAPI Key Function

Update `app/main.py` to use `CF-Connecting-IP` for rate limiting (see code change above).

### Step 6: Configure Cache Rules

Set bypass rules for API paths and cache rules for static assets in the Cloudflare dashboard.

---

## Grapoll Infrastructure With Cloudflare

```
                         ┌─────────────────────────┐
                         │      Cloudflare          │
                         │                          │
User ──── HTTPS ────────►│  DDoS protection         │
                         │  WAF                     │
                         │  CDN cache               │
                         │  SSL termination         │
                         │                          │
                         └────────┬────────┬────────┘
                                  │        │
                           HTTPS  │        │  HTTPS
                                  │        │
                    ┌─────────────▼──┐  ┌──▼──────────────┐
                    │   Frontend     │  │   Fly.io (nrt)   │
                    │   grapoll.kr   │  │   api.grapoll.kr │
                    │                │  │                   │
                    │   Next.js 16   │  │   FastAPI         │
                    └────────────────┘  │   uvicorn :8000   │
                                        └────────┬──────────┘
                                                 │
                                                 │ asyncpg
                                                 │
                                        ┌────────▼──────────┐
                                        │   Supabase        │
                                        │   PostgreSQL 16   │
                                        │   Tokyo           │
                                        └───────────────────┘
```

---

## Related Files

| File | Role |
|------|------|
| `app/main.py` | SlowAPI limiter `key_func` — needs `CF-Connecting-IP` update |
| `fly.toml` | Fly.io config — Cloudflare proxies to `grapoll-api.fly.dev` |
| `Caddyfile` | Only used in Docker Compose self-hosted setup (not Fly.io) |
