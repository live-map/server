# VPN IP Blocking Proposal for Grapoll

## Goal

Restrict poll voting to Korean users only. Block foreign users who use VPNs with Korean server IPs to bypass geo-restriction.

---

## Thought Process

### Initial Assumption: Block All VPN IPs

The first approach considered was maintaining a list of all VPN IP addresses globally. This is impractical — major VPN providers alone operate hundreds of thousands of IPs that rotate constantly. Maintaining this list is a full-time job and exactly what companies like Cloudflare, MaxMind, and IPQualityScore do as their entire business.

### Key Insight: We Only Care About Korean VPN IPs

Grapoll already uses Cloudflare, which adds a `CF-IPCountry` header to every request. Non-Korean IPs are blocked at the Cloudflare level. This means the only VPN IPs we need to worry about are **VPN servers physically located in Korea** — a much smaller set.

### How Many Korean VPN Server IPs Exist?

| Provider | Korean servers (approx) |
|----------|------------------------|
| NordVPN | ~50-100 |
| ExpressVPN | ~10-20 |
| Surfshark | ~10-20 |
| ProtonVPN | ~5-10 |
| CyberGhost | ~20-30 |
| Others combined | ~100-200 |
| **Total** | **~200-400 IPs** |

Compared to hundreds of thousands globally, ~200-400 IPs is a manageable list that can be stored in a database table.

### Remaining Problem: Where to Get the List

You can't manually find 200-400 IPs by subscribing to every VPN provider. Two practical options were considered:

**Option A** — Use a free VPN detection API to build the list automatically over time.

**Option B** — Download a public VPN IP list from sources like `github.com/X4BNet/lists_vpn` and import Korean IPs periodically. Less accurate than paid APIs.

**Decision: Option A** — self-building list using IPQualityScore's free tier (5,000 lookups/month). The list grows organically and only consumes API calls for new, unseen IPs.

---

## Proposed Architecture

```
Request arrives
    |
    v
Layer 1 - Cloudflare: CF-IPCountry != "KR" --> blocked (non-Korean)
    |
    v (Korean IP)
    |
Layer 2 - IPBlockMiddleware: IP in blocked_ips table? --> 403 (known VPN)
    |
    v (not in blocked list)
    |
Layer 3 - Vote endpoint: first-time IP --> API check --> VPN? --> add to DB + reject
    |                                                --> clean? --> allow vote
    |
    v
Layer 4 - Kakao OAuth: proves Korean phone number ownership
```

Three layers, each catching what the previous one missed:

- **Layer 1 (Cloudflare)** — Free. Blocks all non-Korean connections at the edge. Stops casual foreign access instantly.
- **Layer 2 (IP Block Middleware)** — Checks incoming Korean IP against a database of known VPN IPs. O(1) in-memory lookup, no DB query per request. Returns 403 immediately if matched.
- **Layer 3 (Vote endpoint API check)** — For IPs not yet in the blocked list, queries IPQualityScore API to determine if it's a VPN. If yes, adds it to the DB and rejects. If no, allows the vote. This is the self-building mechanism.
- **Layer 4 (Kakao OAuth)** — Kakao accounts require a Korean phone number. Even if all IP-based layers are bypassed, the user must prove Korean identity. This is the last line of defense.

---

## Self-Building VPN IP List

The core mechanism: check once, block forever.

```python
async def check_and_block_vpn(ip: str, session: AsyncSession):
    # Already in blocked list?
    existing = await repo.find_by_ip(ip)
    if existing:
        return True  # blocked

    # Ask API: is this a VPN?
    if await is_vpn_ip(ip):
        # Add to DB — never need to check this IP again
        await repo.create(BlockedIP(
            ip_address=ip,
            reason="VPN detected (auto)",
            blocked_by="system",
        ))
        await session.commit()
        await reload_blocked_ips()  # refresh middleware cache
        return True  # blocked

    return False  # clean IP
```

### How It Works

1. **First time** a VPN IP attempts to vote → API check → detected as VPN → saved to `blocked_ips` table → vote rejected
2. **Second time** the same IP appears → found in DB (via in-memory cache) → blocked instantly at middleware level, no API call needed
3. The list **builds itself** over time as VPN users attempt to vote
4. Free tier (5,000 lookups/month) is sufficient because we only check **new, unseen IPs** — repeat visitors hit the cache

### IPQualityScore API Response Example

```json
{
    "vpn": true,
    "proxy": false,
    "tor": false,
    "country_code": "KR",
    "ISP": "NordVPN",
    "fraud_score": 85
}
```

The API tells us "this IP is Korean, but it belongs to a NordVPN server" — exactly what we need.

---

## Implementation Components

### 1. Database Model — `BlockedIP`

A table to store known VPN/blocked IP addresses.

- `id` — UUID primary key
- `ip_address` — String(45), unique, indexed (45 chars covers IPv6)
- `reason` — why this IP was blocked (e.g., "VPN detected (auto)", "Manual block by admin")
- `blocked_by` — "system" for auto-detected, or admin's user_id for manual blocks
- `created_at` — timestamp

### 2. IP Block Middleware (Pure ASGI)

Runs **before** all other middleware (outermost layer). On every request:

1. Get client IP from `CF-Connecting-IP` header (Cloudflare) or `client.host` (local dev)
2. Check against in-memory `set` of blocked IPs (loaded from DB)
3. Blocked → return 403 immediately (request never reaches FastAPI)
4. Not blocked → pass through to next middleware

The in-memory set refreshes from the DB every 60 seconds and can be force-reloaded by admin endpoints.

### 3. VPN Detection Service

Called at the vote endpoint for IPs not yet in the blocked list. Queries IPQualityScore API and auto-adds detected VPNs to the database.

### 4. Admin Endpoints (CurrentAdmin only)

- `GET /admin/blocked-ips` — list all blocked IPs
- `POST /admin/blocked-ips` — manually block an IP
- `DELETE /admin/blocked-ips/{ip}` — unblock an IP

Allows admins to manually manage the list in addition to the auto-detection system.

---

## Middleware Execution Order

```
Request
    |
    v
IPBlockMiddleware    (outermost — registered last)
    |
    v
SlowAPIMiddleware    (rate limiting)
    |
    v
TokenRefreshMiddleware (JWT refresh)
    |
    v
CORSMiddleware       (innermost — registered first)
    |
    v
Router → Endpoint
```

Blocked IPs are rejected at the very first layer, before any rate limiting, token processing, or CORS handling occurs.

---

## What Each Layer Catches

| Threat | Layer 1 (Cloudflare) | Layer 2 (IP Block) | Layer 3 (API Check) | Layer 4 (Kakao) |
|--------|---------------------|-------------------|-------------------|----------------|
| Foreigner (no VPN) | Blocked | - | - | - |
| Foreigner (Korean VPN, known IP) | Passes | Blocked | - | - |
| Foreigner (Korean VPN, new IP) | Passes | Passes | Blocked + IP saved | - |
| Foreigner (bypasses all IP checks) | Passes | Passes | Passes | Blocked (no Korean phone) |
| Korean user (legitimate) | Passes | Passes | Passes | Passes |

---

## Cost

| Component | Cost |
|-----------|------|
| Cloudflare (free plan) | $0 |
| IPQualityScore (5,000 lookups/month) | $0 |
| Database storage (~400 rows) | Negligible |
| Kakao OAuth | $0 |
| **Total** | **$0** |
