# Authentication Implementation on Backend

## Overview

The backend authentication system uses **stateless JWT tokens** for both access and refresh tokens. All token refresh logic is handled centrally by a middleware layer, so any client (web, mobile, desktop) gets transparent token refresh without implementing its own refresh logic.

---

## Token Design

| Token | Type | Payload | Signed With | Lifetime |
|-------|------|---------|-------------|----------|
| Access | JWT | `{ sub, email, name, role, type: "access" }` | `JWT_SECRET` (HS256) | 30 min |
| Refresh | JWT | `{ sub, email, name, role, type: "refresh" }` | `JWT_SECRET` (HS256) | 30 days |

Both tokens use the same signing secret (`JWT_SECRET`) and algorithm (`HS256`). The `"type"` claim distinguishes them and prevents misuse (e.g., a refresh token cannot be used as an access token because `jwt_guard.py` checks `type == "access"`).

---

## File Structure

```
server/app/api/v1/auth/
├── jwt.py                  # Token creation and decoding
├── jwt_guard.py            # FastAPI dependency for protected routes
├── refresh_middleware.py   # Auto-refresh middleware (stateless)
├── service.py              # OAuth flow and token refresh service
├── controller.py           # HTTP endpoints (/auth/*)
├── oauth.py                # OAuth provider integration
└── dto/
    └── schemas.py          # Request/Response Pydantic models
```

---

## How It Works

### 1. Token Creation (`jwt.py`)

Two functions create tokens:

- **`create_access_token(user_id, email, name, role)`** - Creates a short-lived JWT (30 min) with `type: "access"`.
- **`create_refresh_token(user_id, email, name, role)`** - Creates a long-lived JWT (30 days) with `type: "refresh"`. Both tokens carry the same user claims.

Two functions decode tokens:

- **`decode_access_token(token)`** - Decodes any JWT (does not check `type`).
- **`decode_refresh_token(token)`** - Decodes a JWT and validates that `type == "refresh"`. Raises `jwt.InvalidTokenError` if the type doesn't match.

### 2. Token Refresh Middleware (`refresh_middleware.py`)

The `TokenRefreshMiddleware` is a Starlette `BaseHTTPMiddleware` that intercepts every request and transparently refreshes expired access tokens. It is **fully stateless** - no database lookups are needed.

**Flow:**

```
Request arrives
    │
    ├─ Is it a skipped path? (/api/v1/auth/*, /health, /docs, etc.)
    │   └─ YES → Pass through unchanged
    │
    ├─ Extract access token (from Authorization header or cookie)
    ├─ Extract refresh token (from X-Refresh-Token header or cookie)
    │
    ├─ Is access token valid?
    │   └─ YES → Pass through unchanged
    │
    ├─ Is access token expired/missing AND refresh token present?
    │   ├─ Decode refresh JWT (no DB needed)
    │   ├─ Create new access token from refresh token claims
    │   ├─ Inject new access token into request's Authorization header
    │   └─ After response, add X-New-Access-Token response header
    │
    └─ Both tokens invalid → Pass through (downstream jwt_guard raises 401)
```

**Token extraction sources (in priority order):**

| Token | Source 1 (priority) | Source 2 (fallback) |
|-------|-------------------|-------------------|
| Access | `Authorization: Bearer <token>` header | `grapoll-access-token` / `__Secure-grapoll-access-token` cookie |
| Refresh | `X-Refresh-Token` header | `grapoll-refresh-token` / `__Secure-grapoll-refresh-token` cookie |

**Skipped paths:**
- `/api/v1/auth/*` - Auth endpoints handle their own logic
- `/health`, `/docs`, `/redoc`, `/openapi.json` - Public endpoints
- `/` - Root endpoint

### 3. JWT Guard (`jwt_guard.py`)

FastAPI dependencies that protect routes:

- **`CurrentUser`** (`get_current_user`) - Requires a valid access token. Returns `JWTPayload` with user info. Raises 401 if token is missing, expired, or has wrong type.
- **`CurrentUserOptional`** (`get_current_user_optional`) - Returns `JWTPayload | None`. For routes that work for both authenticated and anonymous users.
- **`CurrentAdmin`** (`get_current_admin`) - Requires valid access token + `role == "ADMIN"`. Raises 403 if not admin.

The guard checks `type == "access"` to prevent refresh tokens from being used as access tokens.

### 4. Auth Service (`service.py`)

**`authenticate_oauth(db, provider, code, redirect_uri)`**
- Full OAuth login flow:
  1. Exchange authorization code for OAuth tokens
  2. Fetch user profile from provider (Google, Kakao)
  3. Find or create user in database
  4. Issue both access and refresh JWTs
- Returns `{ access_token, refresh_token, token_type, user }`.
- No session/token records stored in DB for refresh tokens.

**`refresh_access_token(refresh_token)`**
- Stateless: decodes the refresh JWT and creates a new access token from its claims.
- No DB lookup needed.
- Raises `ValueError` if the refresh token is expired or invalid.

### 5. Auth Controller (`controller.py`)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/oauth/{provider}/authorize` | GET | None | Get OAuth authorization URL |
| `/api/v1/auth/oauth/{provider}/callback` | POST | None | Handle OAuth callback, return tokens |
| `/api/v1/auth/refresh` | POST | None | Explicit refresh (decode JWT, return new access token) |
| `/api/v1/auth/logout` | POST | None | No-op server-side (client clears cookies) |
| `/api/v1/auth/me` | GET | Required | Get current user info from access token |

### 6. CORS Configuration (`main.py`)

The CORS middleware is configured to:
- **Allow header**: `X-Refresh-Token` - So the frontend can send the refresh token.
- **Expose header**: `X-New-Access-Token` - So the frontend JavaScript can read the refreshed token from the response.

### 7. Middleware Stack Order

Starlette processes middleware in reverse order of `add_middleware()` calls:

```python
app.add_middleware(CORSMiddleware, ...)        # 1st: CORS headers
app.add_middleware(TokenRefreshMiddleware)      # 2nd: Token refresh
app.add_middleware(SlowAPIMiddleware)           # 3rd: Rate limiting
# 4th: X-Request-ID (via @app.middleware decorator)
```

Execution order per request: CORS -> TokenRefresh -> RateLimit -> RequestID -> Route handler.

---

## Login Flow (End to End)

```
1. Frontend redirects user to OAuth provider
2. User grants consent, provider redirects back with authorization code
3. Frontend sends code to POST /api/v1/auth/oauth/{provider}/callback
4. Backend exchanges code for OAuth tokens
5. Backend fetches user profile from provider
6. Backend creates/finds user in DB
7. Backend creates access JWT (30 min) + refresh JWT (30 days)
8. Backend returns both tokens to frontend
9. Frontend stores both tokens as httpOnly cookies
```

## Auto-Refresh Flow (End to End)

```
1. Frontend sends request with expired access token + valid refresh token
2. TokenRefreshMiddleware intercepts the request
3. Middleware detects expired access token
4. Middleware decodes refresh JWT (no DB lookup)
5. Middleware creates new access token from refresh claims
6. Middleware injects new access token into request's Authorization header
7. Request proceeds to route handler with valid access token
8. Response includes X-New-Access-Token header with the new token
9. Frontend reads X-New-Access-Token and updates its cookie
```

## Logout Flow

```
1. Frontend calls POST /api/v1/auth/logout (no-op on server)
2. Frontend deletes access and refresh cookies client-side
3. Access token expires naturally in 30 minutes
4. Refresh token expires naturally in 30 days (but cookie is gone)
```

---

## Security Considerations

- **Token type separation**: The `"type"` claim (`"access"` vs `"refresh"`) prevents using a refresh token as an access token. `jwt_guard.py` rejects any token where `type != "access"`.
- **Same secret**: Both tokens use the same `JWT_SECRET`. This is acceptable because the type claim prevents misuse.
- **No server-side revocation**: Logout is client-side only (cookies cleared). If server-side revocation is needed later, a lightweight `revoked_tokens` table can be added.
- **Cookie security**: In production, cookies use the `__Secure-` prefix, `httpOnly`, `secure`, and `sameSite: lax`.
- **Stateless middleware**: The refresh middleware does zero DB calls. This makes it fast and scalable.
