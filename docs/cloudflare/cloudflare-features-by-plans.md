# Cloudflare Features by Plan — Reference for Grapoll

> Last updated: 2026-03-30
> Purpose: Document which Cloudflare features/headers are available at each plan tier,
> so we know what our backend middlewares can rely on.

---

## Plan Pricing Overview

| Plan | Price | Target |
|------|-------|--------|
| **Free** | $0/month | Personal sites |
| **Pro** | $20/month | Professional sites |
| **Business** | $200/month | E-commerce, businesses |
| **Enterprise** | Custom ($$$) | Large-scale, mission-critical |

---

## HTTP Headers Injected by Cloudflare

### Headers Available on ALL Plans (Free, Pro, Business, Enterprise)

These are automatically added to every request passing through Cloudflare:

| Header | Example Value | Description |
|--------|---------------|-------------|
| `CF-Connecting-IP` | `203.0.113.45` | Visitor's real IP address (most reliable source) |
| `CF-Connecting-IPv6` | `2001:db8::1` | Real IPv6 when Pseudo IPv4 is enabled |
| `CF-IPCountry` | `KR` | ISO 3166-1 alpha-2 country code (requires IP Geolocation toggle ON in dashboard) |
| `CF-Ray` | `8f3a2b1c0d4e5f6a-NRT` | Unique request ID + Cloudflare data center code (e.g., NRT = Tokyo) |
| `CF-Visitor` | `{"scheme":"https"}` | JSON with connection scheme |
| `X-Forwarded-For` | `203.0.113.45, 172.68.0.1` | Chain of IPs (client + Cloudflare proxy) |
| `X-Forwarded-Proto` | `https` | Protocol used by visitor |
| `CDN-Loop` | `cloudflare` | Loop detection for multi-CDN setups |

### Managed Transform: Visitor Location Headers (Free+)

Available on all plans when "Add visitor location headers" Managed Transform is enabled:

| Header | Example Value | Description |
|--------|---------------|-------------|
| `cf-ipcity` | `Seoul` | City name |
| `cf-ipcountry` | `KR` | Country code (same as CF-IPCountry) |
| `cf-ipcontinent` | `AS` | Continent code (AF, AN, AS, EU, NA, OC, SA) |
| `cf-iplatitude` | `37.5665` | Approximate latitude |
| `cf-iplongitude` | `126.9780` | Approximate longitude |
| `cf-region` | `Seoul` | Region/state/province name |
| `cf-region-code` | `11` | Region code |
| `cf-postal-code` | `04524` | Postal/ZIP code |
| `cf-timezone` | `Asia/Seoul` | IANA timezone |
| `cf-metro-code` | `0` | Metro code (mainly US) |

### Managed Transform: TLS Client Auth Headers (Free+)

Available on all plans for mTLS (mutual TLS) setups:

| Header | Description |
|--------|-------------|
| `cf-cert-verified` | Certificate verification result |
| `cf-cert-revoked` | Whether cert is revoked |
| `cf-cert-presented` | Whether client presented a cert |
| `cf-cert-issuer-dn` | Issuer distinguished name |
| `cf-cert-subject-dn` | Subject distinguished name |
| `cf-cert-serial` | Certificate serial number |
| `cf-cert-fingerprint-sha256` | SHA-256 fingerprint |
| `cf-cert-not-before` | Validity start date |
| `cf-cert-not-after` | Validity end date |

---

### Pro Plan and Above

| Feature | Header | Description |
|---------|--------|-------------|
| Leaked Credentials Detection | `Exposed-Credential-Check: 1` | Flags requests with exposed username/password combos |

---

### Enterprise Plan Only

| Header | Example Value | Description |
|--------|---------------|-------------|
| `True-Client-IP` | `203.0.113.45` | Enterprise-exclusive real IP header (similar to CF-Connecting-IP) |

### Enterprise + Bot Management Add-On

These require **Enterprise plan + Bot Management subscription** and the "Add bot protection headers" Managed Transform enabled:

| Header | Example Value | Description |
|--------|---------------|-------------|
| `cf-bot-score` | `92` | Bot likelihood score (1–99). See scoring table below. |
| `cf-verified-bot` | `false` | `true` if request is from a known legitimate bot (Googlebot, Bingbot, etc.) |
| `cf-ja3-hash` | `e7d705a3286e19ea42f6...` | JA3 TLS fingerprint — identifies the SSL/TLS client implementation |
| `cf-ja4` | `t13d1516h2_8daaf6152...` | JA4 next-gen TLS fingerprint (more granular than JA3) |

#### `cf-bot-score` Scoring Table

| Score | Category | Meaning |
|-------|----------|---------|
| **0** | Not computed | Bot Management did not run on this request |
| **1** | Automated | Cloudflare is certain this is a bot |
| **2–29** | Likely automated | High probability of bot/script/automation |
| **30–49** | Likely human (low confidence) | Probably human, some anomalies. VPN users often land here. |
| **50–79** | Likely human (medium confidence) | Normal human traffic |
| **80–99** | Likely human (high confidence) | Strong human signals — real browser, standard TLS, etc. |

**Recommended threshold:** Block requests with `cf-bot-score < 30` (the boundary between "likely automated" and "likely human").

#### Bot Management WAF Variables (usable in rules & Workers, not direct headers)

| Variable | Type | Description |
|----------|------|-------------|
| `cf.bot_management.score` | Integer | Same as `cf-bot-score` |
| `cf.bot_management.verified_bot` | Boolean | Same as `cf-verified-bot` |
| `cf.bot_management.ja3_hash` | String | Same as `cf-ja3-hash` |
| `cf.bot_management.ja4` | String | Same as `cf-ja4` |
| `cf.bot_management.corporate_proxy` | Boolean | Identifies cloud-based corporate proxies / secure web gateways |
| `cf.bot_management.static_resource` | Boolean | Whether request targets a static resource (by file extension) |
| `cf.verified_bot_category` | String | Bot category (e.g., "Search Engine Crawler", "Monitoring") |

---

## WAF Features by Plan

### WAF Custom Rules

| Feature | Free | Pro | Business | Enterprise |
|---------|:----:|:---:|:--------:|:----------:|
| Custom rules | 5 | 20 | 100 | 1000 |
| Expression complexity | Basic | Basic | Advanced | Advanced |
| Actions: Block, Challenge, JS Challenge | ✅ | ✅ | ✅ | ✅ |
| Action: Managed Challenge | ✅ | ✅ | ✅ | ✅ |
| Action: Log (no action, just log) | ❌ | ❌ | ❌ | ✅ |

### WAF Managed IP Lists (Enterprise Only)

These are professionally maintained IP lists that can be used in WAF rules:

| List Name | Content | Use Case |
|-----------|---------|----------|
| `cf.vpn` | Commercial VPN exit nodes (NordVPN, ExpressVPN, etc.) | **Block VPN voters** |
| `cf.anonymizer` | VPNs + Tor + open proxies combined | Block all anonymous traffic |
| `cf.open_socks_proxy` | Open SOCKS proxy servers | Block proxy abuse |
| `cf.botnetcc` | Botnet command & control servers | Block malware traffic |
| `cf.malware` | Known malware-distributing IPs | Block malware |

**Important:** These lists are used in WAF rules to **block/challenge at the edge**. They do NOT automatically add headers. To pass VPN detection info to the origin server, a WAF rule must be configured to add a custom header (see `cloudflare-enterprise-setup.md`).

---

## Rate Limiting by Plan

| Feature | Free | Pro | Business | Enterprise |
|---------|:----:|:---:|:--------:|:----------:|
| Rate Limiting Rules | 1 | 2 | 5 | 100+ |
| Counting expressions | Basic | Basic | Advanced | Advanced |
| Complexity | Low | Low | Medium | High |
| Custom responses | ❌ | ❌ | ✅ | ✅ |
| Advanced Rate Limiting | ❌ | ❌ | ❌ | ✅ |

---

## DDoS Protection by Plan

| Feature | Free | Pro | Business | Enterprise |
|---------|:----:|:---:|:--------:|:----------:|
| Layer 3/4 DDoS | ✅ Unmetered | ✅ Unmetered | ✅ Unmetered | ✅ Unmetered |
| Layer 7 DDoS | ✅ Basic | ✅ Basic | ✅ Advanced | ✅ Advanced |
| Adaptive DDoS | ❌ | ❌ | ❌ | ✅ |
| DDoS alerting | ❌ | ❌ | ❌ | ✅ |

---

## Turnstile (CAPTCHA Alternative) — All Plans

Available on **all plans** (separate product, generous free tier):

| Feature | Free | Paid |
|---------|------|------|
| Widget solves | 1M/month | Pay per use |
| Invisible mode | ✅ | ✅ |
| Managed mode | ✅ | ✅ |
| Non-interactive mode | ✅ | ✅ |

---

## Summary: What Matters for Grapoll Vote Protection

### With Free/Pro Plan We Can:
- ✅ Detect and block by country (`CF-IPCountry != KR`)
- ✅ Get accurate client IP (`CF-Connecting-IP`)
- ✅ Get detailed location (city, region, coordinates, timezone)
- ❌ Cannot detect VPN users with Korean exit nodes
- ❌ Cannot detect bots/automation
- ❌ No TLS fingerprinting

### With Enterprise Plan We Additionally Can:
- ✅ Detect and block VPN/proxy users (WAF Managed IP Lists)
- ✅ Detect and block bots (`cf-bot-score < 30`)
- ✅ Identify client software via TLS fingerprinting (`cf-ja3-hash`, `cf-ja4`)
- ✅ Detect corporate proxies
- ✅ Use advanced rate limiting with bot score conditions
- ✅ Get forensic audit data for suspicious votes

---

## References

- [Cloudflare HTTP Headers Reference](https://developers.cloudflare.com/fundamentals/reference/http-headers/)
- [Managed Transforms Reference](https://developers.cloudflare.com/rules/transform/managed-transforms/reference/)
- [Bot Management Documentation](https://developers.cloudflare.com/bots/get-started/bot-management/)
- [Bot Score Concepts](https://developers.cloudflare.com/bots/concepts/bot-score/)
- [Bot Management Variables](https://developers.cloudflare.com/bots/reference/bot-management-variables/)
- [WAF Managed Lists](https://developers.cloudflare.com/waf/tools/lists/managed-lists/)
- [IP Geolocation](https://developers.cloudflare.com/network/ip-geolocation/)
- [Cloudflare Plans & Pricing](https://www.cloudflare.com/plans/)
