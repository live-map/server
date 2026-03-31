# Geo-Restriction Architecture Report for Grapoll

## Goal

Restrict poll voting to Korean users only. Evaluate different architectures for blocking foreign users — including those using Korean VPN servers to bypass geo-restriction.

---

## Background: The VPN Problem

Cloudflare provides `CF-IPCountry` which identifies the country of the incoming IP. Blocking non-Korean IPs is straightforward. The problem is users who use VPN servers located in Korea — Cloudflare sees a Korean IP, but the user is not in Korea.

```
Foreigner without VPN:
    User (US IP) → Cloudflare → CF-IPCountry: US → blocked

Foreigner with Korean VPN:
    User (US IP) → Korean VPN server → Cloudflare → CF-IPCountry: KR → passes
```

---

## Architectures Evaluated

### Architecture A: Cloudflare Free + Kakao OAuth

```
Layer 1: Cloudflare WAF rule — block non-KR on vote endpoints
Layer 2: cf.threat_score — challenge suspicious IPs
Layer 3: Kakao OAuth — Korean phone number required to vote
```

**How each layer works:**

- **Layer 1** — Cloudflare WAF custom rule. Non-Korean IPs are blocked at the edge before reaching the server. Free, no code needed.
  ```
  Expression: (ip.src.country ne "KR") and (http.request.uri.path contains "/api/v1/poll") and (http.request.method eq "POST")
  Action: Block
  ```

- **Layer 2** — `cf.threat_score` is a 0-100 score Cloudflare assigns to every IP. VPN/proxy IPs often score higher because they're shared by many users. Not all VPN IPs have high threat scores, so this is partial detection.
  ```
  Expression: (cf.threat_score gt 10)
  Action: Managed Challenge
  ```

- **Layer 3** — Kakao accounts require a Korean phone number. Even if a foreigner bypasses all IP-based layers with a Korean VPN, they cannot vote without a Kakao account. This is the strongest barrier.

| Threat | Layer 1 | Layer 2 | Layer 3 |
|--------|---------|---------|---------|
| Foreigner (no VPN) | Blocked | — | — |
| Foreigner (Korean VPN, high threat score) | Passes | Challenged | — |
| Foreigner (Korean VPN, low threat score) | Passes | Passes | Blocked (no Korean phone) |
| Korean user (legitimate) | Passes | Passes | Passes |

**Cost: $0/month**

**Strengths:**
- Zero cost
- Kakao phone verification is hard to bypass — stronger than any IP-based solution
- No backend code changes except SlowAPI `key_func`
- No external API dependencies

**Weaknesses:**
- `cf.threat_score` catches some VPN IPs but not all
- No dedicated VPN IP detection
- Relies heavily on Kakao as the primary VPN barrier
- Users who don't have Kakao but are legitimate Koreans (using Google/Discord OAuth) cannot vote

---

### Architecture B: Cloudflare Free + IPQualityScore API (Self-Building VPN List)

```
Layer 1: Cloudflare WAF rule — block non-KR on vote endpoints
Layer 2: IP Block Middleware — check against DB of known VPN IPs
Layer 3: Vote endpoint API check — detect new VPN IPs via IPQualityScore
Layer 4: Kakao OAuth — Korean phone number required to vote
```

**How each layer works:**

- **Layer 1** — Same as Architecture A. Cloudflare blocks non-Korean IPs.

- **Layer 2** — Pure ASGI middleware checks every vote request against an in-memory set of known VPN IPs (loaded from `blocked_ips` DB table). O(1) lookup, no DB query per request. The set refreshes every 60 seconds.

- **Layer 3** — When a new IP (not in the DB) attempts to vote, the vote endpoint calls IPQualityScore API to check if it's a VPN. If yes, the IP is saved to the DB and the vote is rejected. Next time the same IP appears, Layer 2 catches it instantly. The list builds itself over time.

- **Layer 4** — Same as Architecture A. Kakao OAuth as last line of defense.

| Threat | Layer 1 | Layer 2 | Layer 3 | Layer 4 |
|--------|---------|---------|---------|---------|
| Foreigner (no VPN) | Blocked | — | — | — |
| Foreigner (Korean VPN, known IP) | Passes | Blocked | — | — |
| Foreigner (Korean VPN, new IP) | Passes | Passes | Blocked + saved | — |
| Foreigner (bypasses all IP checks) | Passes | Passes | Passes | Blocked |
| Korean user (legitimate) | Passes | Passes | Passes | Passes |

**Cost:**

IPQualityScore pricing (as of 2026):

| Plan | Lookups/Month | Daily Limit | Cost |
|------|-------------|------------|------|
| Free | 1,000 | 35/day | $0 |
| Startup | 5,000 | 250/day | $99/mo |
| SMB Basic | 10,000 | — | $499/mo |

The free tier allows 35 lookups/day. This means 35 new unique IPs can be checked per day — repeat IPs hit the DB cache and don't consume API calls.

- Early stage (few voters): 35/day is likely enough → **$0/month**
- Growing platform (100+ new voters/day): exceeds free tier → **$99/month**

**Strengths:**
- Dedicated VPN detection per IP
- Self-building list gets smarter over time
- Blocks VPN IPs before they reach the vote endpoint (after first detection)
- Combined with Kakao, virtually no way to bypass

**Weaknesses:**
- Free tier limited to 35 new IPs/day — may not scale
- Paid tier jumps to $99/month
- Requires backend implementation (model, middleware, service, admin endpoints)
- External API dependency — if IPQualityScore is down, new VPN IPs slip through (existing ones still blocked from DB)

---

### Architecture C: Cloudflare Enterprise (`cf.vpn` Managed List)

```
Layer 1: Cloudflare WAF rule — block non-KR on vote endpoints
Layer 2: Cloudflare WAF rule — block known VPN IPs using cf.vpn managed list
Layer 3: Kakao OAuth — Korean phone number required to vote
```

**How each layer works:**

- **Layer 1** — Same as above.

- **Layer 2** — Cloudflare maintains a managed list of known VPN server IPs (`cf.vpn`). One WAF rule blocks all VPN traffic on vote endpoints. Cloudflare keeps the list updated — no work on your end.
  ```
  Expression: (ip.src in $cf.vpn) and (http.request.uri.path contains "/api/v1/poll") and (http.request.method eq "POST")
  Action: Block
  ```

- **Layer 3** — Kakao OAuth.

| Threat | Layer 1 | Layer 2 | Layer 3 |
|--------|---------|---------|---------|
| Foreigner (no VPN) | Blocked | — | — |
| Foreigner (Korean VPN) | Passes | Blocked | — |
| Foreigner (unknown VPN not in cf.vpn) | Passes | Passes | Blocked |
| Korean user (legitimate) | Passes | Passes | Passes |

**Cost: ~$200+/month** (Cloudflare Enterprise, custom pricing)

**Strengths:**
- Best VPN detection — Cloudflare maintains the list professionally
- Zero backend code changes
- Blocks at the edge (request never reaches your server)
- No external API calls from your application
- Additional Enterprise features: bot management, WAF attack score, advanced analytics

**Weaknesses:**
- $200+/month minimum (custom pricing, requires contacting sales)
- Overkill for an early-stage platform
- `cf.vpn` list may still miss some VPN IPs (no list is 100% complete)

---

## Feature Comparison by Plan Level

Cloudflare plan features relevant to VPN detection:

| Feature | Free | Pro ($20/mo) | Business ($200/mo) | Enterprise |
|---------|------|-------------|-------------------|-----------|
| `ip.src.country` (geo-restriction) | Yes | Yes | Yes | Yes |
| `cf.threat_score` | Yes | Yes | Yes | Yes |
| `ip.src.asnum` (ASN blocking) | Yes | Yes | Yes | Yes |
| Custom WAF rules | 5 | 20 | 100 | 1000 |
| Bot Fight Mode | Yes | Yes | Yes | Yes |
| Super Bot Fight Mode | No | Yes | Yes | Yes |
| WAF Attack Score | No | No | Limited | Full |
| Managed VPN list (`cf.vpn`) | No | No | No | **Yes** |
| Managed Anonymizer list (`cf.anonymizer`) | No | No | No | **Yes** |

**Key takeaway:** Pro ($20/mo) adds almost nothing for VPN detection compared to Free. The meaningful jump is to Enterprise for `cf.vpn`.

---

## Korean VPN Server IP Scale

The number of VPN server IPs physically located in Korea is relatively small:

| Provider | Korean Servers (approx) |
|----------|------------------------|
| NordVPN | ~50-100 |
| ExpressVPN | ~10-20 |
| Surfshark | ~10-20 |
| ProtonVPN | ~5-10 |
| CyberGhost | ~20-30 |
| Others combined | ~100-200 |
| **Total** | **~200-400 IPs** |

This is manageable compared to hundreds of thousands globally. Architecture B's self-building approach can realistically capture most of these over time.

---

## Recommendation

### For Now (Early Stage): Architecture A

```
Cloudflare Free (geo + threat score) + Kakao OAuth
Cost: $0
```

Kakao's Korean phone number requirement is the strongest single barrier against foreign voters. No VPN can bypass a phone number check. Start with this and monitor if actual abuse occurs.

The only gap: legitimate Korean users who use Google/Discord OAuth instead of Kakao cannot vote. If this is acceptable, Architecture A is sufficient.

### If Abuse Is Detected: Architecture B

```
Cloudflare Free + IPQualityScore + Kakao OAuth
Cost: $0 (free tier) or $99/mo (if traffic exceeds 35 new IPs/day)
```

Add the self-building VPN IP list only if you observe actual vote manipulation from Korean VPN IPs getting past Kakao. This requires backend implementation but provides dedicated VPN detection.

### If Budget Allows: Architecture C

```
Cloudflare Enterprise
Cost: $200+/mo
```

The cleanest solution — Cloudflare handles everything, no backend code. Only worth it if Grapoll has revenue to justify the cost and needs the additional Enterprise features (advanced bot management, WAF attack score, SLA guarantees).

---

## Summary Table

| | Architecture A | Architecture B | Architecture C |
|--|---------------|---------------|---------------|
| **Approach** | Cloudflare Free + Kakao | Cloudflare Free + IPQS API + Kakao | Cloudflare Enterprise + Kakao |
| **VPN Detection** | Partial (threat score) | Good (self-building list) | Best (managed list) |
| **Monthly Cost** | $0 | $0-99 | $200+ |
| **Backend Code Changes** | SlowAPI `key_func` only | Model + Middleware + Service + Admin endpoints | SlowAPI `key_func` only |
| **Maintenance** | None | DB table grows automatically | None (Cloudflare maintains) |
| **Identity Verification** | Kakao phone number | Kakao phone number | Kakao phone number |
| **Best For** | Early stage, $0 budget | Growing platform with abuse | Funded platform |
