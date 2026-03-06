# Authentication Implementation on Backend — Detailed Code Walkthrough

## Overview

The backend authentication system uses **stateless JWT tokens** for both access and refresh tokens. All token refresh logic is handled centrally by a middleware layer, so any client (web, mobile, desktop) gets transparent token refresh without implementing its own refresh logic.

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌────────┐
│  Client   │────▸│ FastAPI  │────▸│ OAuth Provider│     │   DB   │
│(Frontend) │◂────│ Backend  │◂────│ (Google/Kakao)│     │(Postgres)│
└──────────┘     └──────────┘     └──────────────┘     └────────┘
```

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
server/app/
├── api/v1/auth/
│   ├── jwt.py                  # Token creation and decoding
│   ├── jwt_guard.py            # FastAPI dependency for protected routes
│   ├── refresh_middleware.py   # Auto-refresh middleware (stateless, pure ASGI)
│   ├── service.py              # OAuth flow and token refresh service
│   ├── controller.py           # HTTP endpoints (/auth/*)
│   ├── oauth.py                # OAuth provider integration (Authlib)
│   └── dto/
│       └── schemas.py          # Request/Response Pydantic models
├── core/
│   └── config.py               # Settings (JWT_SECRET, token expiry, OAuth credentials)
├── models/
│   ├── user.py                 # User model (SQLAlchemy)
│   └── account.py              # Account model (OAuth provider link)
└── main.py                     # App entry point, middleware stack, CORS
```

---

## 1. Application Configuration (`core/config.py`)

### File: `server/app/core/config.py`

```python
class Settings(BaseSettings):                                           # [1]
    model_config = SettingsConfigDict(                                   # [2]
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Grapoll API"                                       # [3]
    DEBUG: bool = False                                                  # [4]

    # JWT Configuration
    JWT_SECRET: str = ""                                                 # [5]
    JWT_ALGORITHM: str = "HS256"                                         # [6]
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30                                # [7]
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30                                  # [8]

    # Frontend URL for CORS and cookie settings
    FRONTEND_URL: AnyHttpUrl = "http://localhost:3000"                   # [9]

    GOOGLE_CLIENT_ID: str = ""                                           # [10]
    GOOGLE_CLIENT_SECRET: str = ""                                       # [11]
    KAKAO_CLIENT_ID: str = ""                                            # [12]
    KAKAO_CLIENT_SECRET: str = ""                                        # [13]

settings = Settings()                                                    # [14]
```

**Line-by-line:**

| Line | Explanation |
|------|-------------|
| `[1]` | `BaseSettings` from Pydantic — automatically loads values from environment variables and `.env` file. |
| `[2]` | Configuration: load `.env` file with UTF-8 encoding, ignore unknown env vars (`extra="ignore"`). |
| `[3]` | Application name used in API docs and health check. |
| `[4]` | Debug mode — when `True`, error responses include exception type names. |
| `[5]` | **JWT signing secret** — used by both `create_access_token()` and `create_refresh_token()`. Must be a strong random string (e.g., `openssl rand -hex 32`). All JWTs are signed and verified with this key. |
| `[6]` | JWT algorithm — `HS256` (HMAC-SHA256). Symmetric algorithm: same key for signing and verification. |
| `[7]` | Access token lifetime — 30 minutes. After this, the token is expired and the middleware will attempt to refresh it. |
| `[8]` | Refresh token lifetime — 30 days. The user can stay logged in for this long without re-authenticating. |
| `[9]` | Frontend URL — used in CORS middleware to allow cross-origin requests from the Next.js app. |
| `[10]-[13]` | OAuth provider credentials — registered in Google Cloud Console and Kakao Developer portal. `client_id` is public, `client_secret` is private (only used server-side). |
| `[14]` | Singleton settings instance — imported throughout the app as `from app.core.config import settings`. |

---

## 2. Token Creation and Decoding (`jwt.py`)

### File: `server/app/api/v1/auth/jwt.py`

```python
"""
JWT token creation and validation.

Issues access tokens (short-lived) and refresh tokens (long-lived)
using PyJWT with HS256 signing. Both token types are JWTs
distinguished by the "type" claim ("access" vs "refresh").
"""

import logging                                                          # [1]
from datetime import datetime, timedelta, timezone                      # [2]

import jwt                                                              # [3]

from app.core.config import settings                                    # [4]

logger = logging.getLogger(__name__)                                    # [5]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Standard logging for debug messages. |
| `[2]` | `datetime` and `timedelta` for computing token expiration times. `timezone` for UTC-aware timestamps. |
| `[3]` | PyJWT library — encodes/decodes JWT tokens. Not to be confused with `jwt` the module name (the package is `PyJWT`). |
| `[4]` | Import settings for `JWT_SECRET`, `JWT_ALGORITHM`, and token expiry durations. |
| `[5]` | Logger scoped to this module's name. |

### `create_access_token()`

```python
def create_access_token(                                                # [1]
    user_id: str, email: str | None, name: str | None, role: str
) -> str:
    now = datetime.now(timezone.utc)                                    # [2]
    payload = {
        "sub": user_id,                                                 # [3]
        "email": email,                                                 # [4]
        "name": name,                                                   # [5]
        "role": role,                                                   # [6]
        "type": "access",                                               # [7]
        "iat": now,                                                     # [8]
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), # [9]
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM) # [10]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Create a short-lived access token. Takes user data as parameters — these become JWT claims. Returns a signed JWT string. |
| `[2]` | Get the current UTC time. Used for both `iat` (issued at) and computing `exp` (expiration). Always UTC to avoid timezone issues. |
| `[3]` | `sub` (subject) — Standard JWT claim (RFC 7519). Contains the user's CUID from the database. This is the primary identifier used by the JWT guard to identify the user. |
| `[4]` | `email` — User's email. Embedded in the token so the backend doesn't need a DB lookup for basic user info. Can be `None` if the OAuth provider doesn't provide it. |
| `[5]` | `name` — User's display name from the OAuth provider. |
| `[6]` | `role` — `"USER"` or `"ADMIN"`. Used by the `CurrentAdmin` guard to enforce admin-only routes. |
| `[7]` | `type: "access"` — Custom claim that distinguishes access tokens from refresh tokens. The JWT guard (`jwt_guard.py`) checks this claim and rejects any token where `type != "access"`. This prevents a refresh token from being used as an access token, even though both are signed with the same `JWT_SECRET`. |
| `[8]` | `iat` (issued at) — Standard JWT claim. Records when the token was created. |
| `[9]` | `exp` (expiration) — Standard JWT claim. PyJWT automatically checks this during decoding and raises `ExpiredSignatureError` if the current time is past this value. Default: 30 minutes from now. |
| `[10]` | `jwt.encode()` — Signs the payload with `JWT_SECRET` using `HS256` (HMAC-SHA256). Returns a base64url-encoded string like `eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOi...`. Only the server (which knows `JWT_SECRET`) can create or verify these tokens. |

### `create_refresh_token()`

```python
def create_refresh_token(                                               # [1]
    user_id: str, email: str | None, name: str | None, role: str
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "type": "refresh",                                              # [2]
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),# [3]
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM) # [4]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Create a long-lived refresh token. Same signature as `create_access_token()` — takes the same user data. |
| `[2]` | `type: "refresh"` — Distinguishes this from access tokens. The `decode_refresh_token()` function validates this claim. If someone tries to use an access token as a refresh token, it will be rejected. |
| `[3]` | Expires in 30 days (vs 30 minutes for access tokens). During this 30-day window, the auto-refresh middleware can use this token to create new access tokens without requiring the user to re-login. |
| `[4]` | Signed with the same `JWT_SECRET` and algorithm. The `type` claim is what prevents misuse — not different keys. |

### `decode_access_token()`

```python
def decode_access_token(token: str) -> dict:                            # [1]
    return jwt.decode(                                                  # [2]
        token,
        settings.JWT_SECRET,                                            # [3]
        algorithms=[settings.JWT_ALGORITHM],                            # [4]
    )
```

| Line | Explanation |
|------|-------------|
| `[1]` | Decode any JWT token. Despite the name, this doesn't check `type` — it just verifies the signature and expiration. Used by the JWT guard and middleware. |
| `[2]` | `jwt.decode()` — Verifies the HMAC signature, checks `exp` (raises `ExpiredSignatureError` if expired), and returns the decoded payload dict. |
| `[3]` | Must match the secret used to encode. If the token was tampered with (different secret), raises `InvalidTokenError`. |
| `[4]` | `algorithms` is a list — must explicitly specify allowed algorithms to prevent algorithm confusion attacks (e.g., an attacker changing the algorithm to `"none"`). |

### `decode_refresh_token()`

```python
def decode_refresh_token(token: str) -> dict:                           # [1]
    payload = jwt.decode(                                               # [2]
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
    if payload.get("type") != "refresh":                                # [3]
        raise jwt.InvalidTokenError("Not a refresh token")             # [4]
    return payload                                                      # [5]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Decode and validate a refresh token specifically. Used by the refresh middleware and the explicit `/refresh` endpoint. |
| `[2]` | Standard JWT decode — verifies signature and expiration. Raises `ExpiredSignatureError` if the 30-day window has passed. |
| `[3]` | **Type guard** — checks that the decoded token has `type == "refresh"`. This prevents an access token from being used as a refresh token. |
| `[4]` | If the type doesn't match, raise `InvalidTokenError`. The middleware catches this and skips refresh. |
| `[5]` | Return the full payload: `{ sub, email, name, role, type, iat, exp }`. The middleware uses `sub`, `email`, `name`, and `role` to create a new access token. |

---

## 3. OAuth Provider Integration (`oauth.py`)

### File: `server/app/api/v1/auth/oauth.py`

### Provider Configuration

```python
OAUTH_PROVIDERS: dict[str, dict] = {                                    # [1]
    "google": {
        "client_id": settings.GOOGLE_CLIENT_ID,                         # [2]
        "client_secret": settings.GOOGLE_CLIENT_SECRET,                 # [3]
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",# [4]
        "token_url": "https://oauth2.googleapis.com/token",             # [5]
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",# [6]
        "scope": "openid email profile",                                # [7]
    },
    "kakao": {
        "client_id": settings.KAKAO_CLIENT_ID,
        "client_secret": settings.KAKAO_CLIENT_SECRET,
        "authorize_url": "https://kauth.kakao.com/oauth/authorize",
        "token_url": "https://kauth.kakao.com/oauth/token",
        "userinfo_url": "https://kapi.kakao.com/v2/user/me",
        "scope": "profile_nickname profile_image account_email",        # [8]
    },
}
```

| Line | Explanation |
|------|-------------|
| `[1]` | Central registry of supported OAuth providers. Adding a new provider (e.g., Discord) requires adding an entry here. |
| `[2]` | `client_id` — Public app identifier registered with the provider. Included in the authorization URL and token exchange request. |
| `[3]` | `client_secret` — Private app secret. Only used server-side during token exchange. Never sent to the browser. |
| `[4]` | `authorize_url` — Google's authorization endpoint. Users are redirected here to grant consent. Displays Google's consent screen. |
| `[5]` | `token_url` — Google's token endpoint. The backend sends the authorization code here (via POST) to receive an OAuth access token. |
| `[6]` | `userinfo_url` — Google's resource server. After getting the OAuth access token, the backend fetches the user's profile (name, email, picture) from here. |
| `[7]` | `scope` — Permissions requested from Google. `openid` = OpenID Connect, `email` = email address, `profile` = name and picture. |
| `[8]` | Kakao scopes use different naming: `profile_nickname` = display name, `profile_image` = profile photo, `account_email` = email address. |

### `get_provider_config()`

```python
def get_provider_config(provider: str) -> dict:                         # [1]
    config = OAUTH_PROVIDERS.get(provider)                              # [2]
    if not config:
        raise ValueError(f"Unsupported OAuth provider: {provider}")     # [3]
    return config
```

| Line | Explanation |
|------|-------------|
| `[1]` | Lookup function for provider configuration. Used by all other functions in this module. |
| `[2]` | Dictionary lookup — returns `None` if provider not found. |
| `[3]` | Raise `ValueError` for unsupported providers. The controller catches this and returns 400 Bad Request. |

### `create_oauth_client()`

```python
def create_oauth_client(provider: str, redirect_uri: str) -> AsyncOAuth2Client: # [1]
    config = get_provider_config(provider)                              # [2]
    return AsyncOAuth2Client(                                           # [3]
        client_id=config["client_id"],                                  # [4]
        client_secret=config["client_secret"],                          # [5]
        redirect_uri=redirect_uri,                                      # [6]
        scope=config["scope"],                                          # [7]
    )
```

| Line | Explanation |
|------|-------------|
| `[1]` | Factory function that creates an Authlib `AsyncOAuth2Client`. Authlib is a comprehensive OAuth library that handles protocol details. |
| `[2]` | Get the provider's configuration (client_id, URLs, scope). |
| `[3]` | `AsyncOAuth2Client` — Authlib's async HTTP client with OAuth 2.0 protocol support built in. Handles PKCE, state, code challenge, and token parsing. |
| `[4]` | `client_id` — Identifies our app to the OAuth provider. |
| `[5]` | `client_secret` — Authenticates our app during token exchange. |
| `[6]` | `redirect_uri` — Must match exactly what was registered in the OAuth provider's developer console. |
| `[7]` | `scope` — Permissions to request. |

### `get_authorization_url()`

```python
def get_authorization_url(                                              # [1]
    provider: str, redirect_uri: str, state: str
) -> str:
    config = get_provider_config(provider)                              # [2]
    client = create_oauth_client(provider, redirect_uri)                # [3]
    url, _ = client.create_authorization_url(                           # [4]
        config["authorize_url"],                                        # [5]
        state=state,                                                    # [6]
    )
    return url                                                          # [7]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Generate the full OAuth authorization URL. Called by the controller's `GET /oauth/{provider}/authorize` endpoint. |
| `[2]` | Look up provider config. |
| `[3]` | Create an OAuth2 client with credentials and redirect URI. |
| `[4]` | `create_authorization_url()` — Authlib builds the URL with all required OAuth 2.0 parameters: `response_type=code`, `client_id`, `redirect_uri`, `scope`, and `state`. Returns a tuple `(url, state)` — we already have state, so discard the second value with `_`. |
| `[5]` | Base URL to append query parameters to. Google: `https://accounts.google.com/o/oauth2/v2/auth`. |
| `[6]` | `state` — CSRF protection token. A random string generated by the controller. The OAuth provider echoes it back in the callback, allowing the frontend to verify the request wasn't forged. |
| `[7]` | Return the complete URL. Example: `https://accounts.google.com/o/oauth2/v2/auth?client_id=xxx&redirect_uri=http://localhost:3000/api/auth/callback/google&scope=openid+email+profile&state=abc123&response_type=code`. |

### `exchange_code_for_token()`

```python
async def exchange_code_for_token(                                      # [1]
    provider: str, code: str, redirect_uri: str
) -> dict:
    config = get_provider_config(provider)                              # [2]
    client = create_oauth_client(provider, redirect_uri)                # [3]

    token = await client.fetch_token(                                   # [4]
        config["token_url"],                                            # [5]
        code=code,                                                      # [6]
    )
    return dict(token)                                                  # [7]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Exchange an authorization code for an OAuth access token. This is the core of the Authorization Code Grant. Async because it makes an HTTP request to the provider. |
| `[2]` | Get provider config for the token URL. |
| `[3]` | Create OAuth client. The `redirect_uri` must match exactly what was used in the authorization URL — the provider verifies this. |
| `[4]` | `fetch_token()` — Authlib sends a POST request to the token endpoint with: `grant_type=authorization_code`, `code`, `client_id`, `client_secret`, and `redirect_uri`. The provider validates the code and returns tokens. |
| `[5]` | Token endpoint URL. Google: `https://oauth2.googleapis.com/token`. Kakao: `https://kauth.kakao.com/oauth/token`. |
| `[6]` | The one-time authorization code. Valid for a few minutes. Can only be used once. |
| `[7]` | Convert to a plain dict. Contains: `{ access_token, refresh_token, expires_at, id_token, token_type, scope }`. These are the **OAuth provider's tokens** — used to call the provider's API. Not to be confused with our own JWTs. |

### `fetch_user_profile()`

```python
async def fetch_user_profile(                                           # [1]
    provider: str, access_token: str
) -> dict:
    config = get_provider_config(provider)                              # [2]

    async with AsyncOAuth2Client(                                       # [3]
        token={"access_token": access_token, "token_type": "Bearer"}    # [4]
    ) as client:
        resp = await client.get(config["userinfo_url"])                 # [5]
        resp.raise_for_status()                                         # [6]
        data = resp.json()                                              # [7]

    if provider == "google":                                            # [8]
        return {
            "provider_account_id": data["sub"],                         # [9]
            "email": data.get("email"),                                 # [10]
            "name": data.get("name"),                                   # [11]
            "image": data.get("picture"),                               # [12]
        }
    elif provider == "kakao":                                           # [13]
        account = data.get("kakao_account", {})                         # [14]
        profile = account.get("profile", {})                            # [15]
        return {
            "provider_account_id": str(data["id"]),                     # [16]
            "email": account.get("email"),                              # [17]
            "name": profile.get("nickname"),                            # [18]
            "image": profile.get("profile_image_url"),                  # [19]
        }
    else:
        raise ValueError(f"Unsupported provider for profile parsing: {provider}") # [20]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Fetch the user's profile from the OAuth provider's resource server. Called after successfully exchanging the code for tokens. |
| `[2]` | Get provider config for the userinfo URL. |
| `[3]` | Create an Authlib client pre-configured with the OAuth access token. `async with` ensures the underlying HTTP connection is properly closed after use. |
| `[4]` | Set the token for automatic `Authorization: Bearer <token>` header injection on requests. |
| `[5]` | GET the user's profile. Google: `https://www.googleapis.com/oauth2/v3/userinfo`. Kakao: `https://kapi.kakao.com/v2/user/me`. |
| `[6]` | Raise an exception if the request failed (e.g., token revoked, API error). |
| `[7]` | Parse the JSON response body. |
| `[8]` | **Google normalization** — Google returns a flat JSON object. |
| `[9]` | `data["sub"]` — Google's unique user ID (numeric string like `"117..."` ). Used as `provider_account_id` to link this Google account to a user in our database. |
| `[10]` | `data.get("email")` — User's email. Uses `.get()` because email might not be present (user didn't grant email scope, or email is unverified). |
| `[11]` | `data.get("name")` — User's display name from Google profile. |
| `[12]` | `data.get("picture")` — URL of the user's Google profile picture. |
| `[13]` | **Kakao normalization** — Kakao returns a deeply nested JSON structure. |
| `[14]` | User profile data is nested inside `kakao_account`. |
| `[15]` | Display name and image are further nested inside `kakao_account.profile`. |
| `[16]` | `data["id"]` — Kakao's unique user ID (integer). Converted to string for consistent `provider_account_id` type. |
| `[17]` | Email from `kakao_account.email`. |
| `[18]` | Display name from `kakao_account.profile.nickname`. |
| `[19]` | Profile image URL from `kakao_account.profile.profile_image_url`. |
| `[20]` | Safety check — if a new provider is added to `OAUTH_PROVIDERS` but profile parsing isn't implemented, fail explicitly. |

---

## 4. Auth Service (`service.py`)

### File: `server/app/api/v1/auth/service.py`

### Imports

```python
import logging                                                          # [1]

from sqlalchemy import select                                           # [2]
from sqlalchemy.ext.asyncio import AsyncSession                         # [3]

from app.models.account import Account                                  # [4]
from app.models.user import Role, User                                  # [5]
from app.api.v1.auth.jwt import (                                       # [6]
    create_access_token, create_refresh_token, decode_refresh_token
)
from app.api.v1.auth.oauth import exchange_code_for_token, fetch_user_profile # [7]

logger = logging.getLogger(__name__)                                    # [8]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Standard logging. |
| `[2]` | SQLAlchemy `select` — used to build SELECT queries. |
| `[3]` | `AsyncSession` — async database session for non-blocking DB operations. |
| `[4]` | `Account` model — stores OAuth provider credentials linked to users. |
| `[5]` | `User` model and `Role` enum (`USER`, `ADMIN`). |
| `[6]` | JWT functions from `jwt.py`. |
| `[7]` | OAuth functions from `oauth.py`. |
| `[8]` | Module-scoped logger. |

### `get_or_create_user()`

```python
async def get_or_create_user(                                           # [1]
    db: AsyncSession,
    provider: str,
    profile: dict,
    oauth_tokens: dict,
) -> User:
    provider_account_id = profile["provider_account_id"]                # [2]

    # Check if this OAuth account is already linked to a user
    result = await db.execute(                                          # [3]
        select(User)                                                    # [4]
        .join(Account, Account.user_id == User.id)                      # [5]
        .where(Account.provider == provider)                            # [6]
        .where(Account.provider_account_id == provider_account_id)      # [7]
    )
    user = result.scalar_one_or_none()                                  # [8]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Find an existing user or create a new one. This handles three cases: (1) returning user with same provider, (2) existing user linking new provider, (3) brand new user. |
| `[2]` | Extract the provider's unique user ID (e.g., Google's `sub` or Kakao's `id`). |
| `[3]` | Execute an async SQL query. |
| `[4]` | `select(User)` — We want to return a `User` object. |
| `[5]` | JOIN `users` with `accounts` on `user_id` — to find which user owns the OAuth account. |
| `[6]` | Filter by provider name (e.g., `"google"`). |
| `[7]` | Filter by provider account ID. Together with `[6]`, this uniquely identifies one OAuth account. |
| `[8]` | `scalar_one_or_none()` — Returns the `User` if found, `None` if no match. Raises if multiple found (shouldn't happen due to unique constraint). |

```python
    if user:                                                            # [1]
        logger.info(f"Returning user found by OAuth account: {user.id}")
        # Update OAuth tokens on the account
        account_result = await db.execute(                              # [2]
            select(Account)
            .where(Account.provider == provider)
            .where(Account.provider_account_id == provider_account_id)
        )
        account = account_result.scalar_one()                           # [3]
        account.access_token = oauth_tokens.get("access_token")         # [4]
        account.refresh_token = oauth_tokens.get("refresh_token")       # [5]
        account.expires_at = oauth_tokens.get("expires_at")             # [6]
        account.id_token = oauth_tokens.get("id_token")                 # [7]
        await db.commit()                                               # [8]
        return user                                                     # [9]
```

| Line | Explanation |
|------|-------------|
| `[1]` | **Case 1: Returning user** — User has logged in with this provider before. |
| `[2]` | Query the Account record to update its stored tokens. |
| `[3]` | `scalar_one()` — Must exist (we just found it via JOIN). |
| `[4]-[7]` | Update the stored **OAuth provider tokens**. These are the provider's tokens (for making API calls to Google/Kakao), not our JWTs. The provider issues fresh tokens each login. |
| `[8]` | Commit the updated tokens to the database. |
| `[9]` | Return the existing user. |

```python
    # Check if a user with this email already exists (link account)
    if profile.get("email"):                                            # [1]
        result = await db.execute(
            select(User).where(User.email == profile["email"])          # [2]
        )
        user = result.scalar_one_or_none()

    if user:                                                            # [3]
        logger.info(f"Linking new OAuth account to existing user: {user.id}")
    else:
        # Create new user
        from cuid2 import cuid_wrapper                                  # [4]
        generate_cuid = cuid_wrapper()                                  # [5]
        user = User(                                                    # [6]
            id=generate_cuid(),                                         # [7]
            name=profile.get("name"),                                   # [8]
            email=profile.get("email"),
            image=profile.get("image"),
            role=Role.USER,                                             # [9]
        )
        db.add(user)                                                    # [10]
        await db.flush()                                                # [11]
        logger.info(f"Created new user: {user.id}")
```

| Line | Explanation |
|------|-------------|
| `[1]` | **Case 2: Account linking** — No OAuth account found, but check if a user with the same email exists. Example: user first logged in with Google, now tries Kakao with the same email. |
| `[2]` | Look up user by email. |
| `[3]` | If found, we'll link the new OAuth account to this existing user. |
| `[4]` | Import CUID2 — collision-resistant unique ID generator. Lazy import to avoid circular dependencies. |
| `[5]` | Create a CUID generator function. |
| `[6]` | **Case 3: New user** — Create a `User` model instance. |
| `[7]` | Generate a CUID as the primary key (e.g., `"clx9ab2c3d0001..."`). Compatible with Prisma's default CUID format. |
| `[8]` | Populate user data from the OAuth profile. |
| `[9]` | Default role is `Role.USER`. The `Role` enum maps to PostgreSQL's custom enum type `"Role"`. |
| `[10]` | `db.add()` — Mark the user for INSERT. Not yet written to DB. |
| `[11]` | `flush()` — Execute the INSERT immediately without committing the transaction. This ensures `user.id` is available for the Account foreign key. The transaction is committed later after the Account is also added. |

```python
    # Link OAuth account
    from cuid2 import cuid_wrapper
    generate_cuid = cuid_wrapper()
    account = Account(                                                  # [1]
        id=generate_cuid(),                                             # [2]
        user_id=user.id,                                                # [3]
        type="oauth",                                                   # [4]
        provider=provider,                                              # [5]
        provider_account_id=provider_account_id,                        # [6]
        access_token=oauth_tokens.get("access_token"),                  # [7]
        refresh_token=oauth_tokens.get("refresh_token"),
        expires_at=oauth_tokens.get("expires_at"),
        token_type=oauth_tokens.get("token_type"),
        scope=oauth_tokens.get("scope"),
        id_token=oauth_tokens.get("id_token"),
    )
    db.add(account)                                                     # [8]
    await db.commit()                                                   # [9]

    return user                                                         # [10]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Create a new `Account` record linking the OAuth provider to the user. |
| `[2]` | Generate a CUID for the account's primary key. |
| `[3]` | `user_id` — Foreign key linking to the User. For new users, this was set by `flush()`. For existing users, this is their existing ID. |
| `[4]` | `type: "oauth"` — Account type. Always `"oauth"` for OAuth logins. |
| `[5]` | Provider name — `"google"` or `"kakao"`. |
| `[6]` | Provider's unique user ID — used together with `provider` as a unique constraint to prevent duplicate accounts. |
| `[7]` | Store the provider's tokens. These are used if the backend later needs to call the provider's API on behalf of the user. |
| `[8]` | Mark the account for INSERT. |
| `[9]` | Commit both the user (if new) and the account in a single transaction. If anything fails, both are rolled back. |
| `[10]` | Return the User model instance. |

### `authenticate_oauth()`

```python
async def authenticate_oauth(                                           # [1]
    db: AsyncSession,
    provider: str,
    code: str,
    redirect_uri: str,
) -> dict:
    # Step 1: Exchange code for OAuth tokens
    oauth_tokens = await exchange_code_for_token(                       # [2]
        provider, code, redirect_uri
    )

    # Step 2: Fetch user profile from resource server
    profile = await fetch_user_profile(                                 # [3]
        provider, oauth_tokens["access_token"]
    )

    # Step 3: Find or create user
    user = await get_or_create_user(db, provider, profile, oauth_tokens) # [4]

    # Step 4: Issue our own tokens (both are stateless JWTs)
    access_token = create_access_token(                                 # [5]
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
    )
    refresh_token = create_refresh_token(                               # [6]
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
    )

    return {                                                            # [7]
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "image": user.image,
            "role": user.role,
        },
    }
```

| Line | Explanation |
|------|-------------|
| `[1]` | Main orchestration function for the OAuth login flow. Called by the controller's callback endpoint. |
| `[2]` | **Step 1**: Send the authorization code to the OAuth provider's token endpoint. Get back the provider's access/refresh tokens. This is a server-to-server call (the code is exchanged for tokens securely). |
| `[3]` | **Step 2**: Use the provider's access token to fetch the user's profile. Returns normalized data: `{ provider_account_id, email, name, image }`. |
| `[4]` | **Step 3**: Look up the user in our database or create a new one. Handles returning users, account linking, and new registrations. |
| `[5]` | **Step 4a**: Create our access JWT (30 min). Embeds user claims so downstream services can identify the user without a DB call. |
| `[6]` | **Step 4b**: Create our refresh JWT (30 days). Same claims but longer lifetime and `type: "refresh"`. |
| `[7]` | Return everything to the controller. The controller serializes this as JSON to the frontend. |

### `refresh_access_token()`

```python
def refresh_access_token(refresh_token: str) -> dict:                   # [1]
    import jwt                                                          # [2]

    try:
        payload = decode_refresh_token(refresh_token)                   # [3]
    except jwt.ExpiredSignatureError:                                   # [4]
        raise ValueError("Refresh token has expired")
    except jwt.InvalidTokenError as e:                                  # [5]
        raise ValueError(f"Invalid refresh token: {e}")

    access_token = create_access_token(                                 # [6]
        user_id=payload["sub"],
        email=payload.get("email"),
        name=payload.get("name"),
        role=payload.get("role", "USER"),
    )

    return {                                                            # [7]
        "access_token": access_token,
        "token_type": "Bearer",
    }
```

| Line | Explanation |
|------|-------------|
| `[1]` | Validate a refresh token and issue a new access token. **Synchronous** (not `async`) — no DB lookup needed. Fully stateless. Used by the explicit `/refresh` endpoint. |
| `[2]` | Import PyJWT for exception types. |
| `[3]` | Decode the refresh JWT. Validates signature, expiration, and `type == "refresh"`. |
| `[4]` | If the refresh token's 30-day window has passed, raise `ValueError`. The controller converts this to a 401 HTTP response. |
| `[5]` | If the token is tampered with or malformed, raise `ValueError`. |
| `[6]` | Create a new access token using the claims from the refresh token. The new access token has fresh `iat` and `exp` timestamps (another 30 minutes). |
| `[7]` | Return the new access token. The frontend stores this in its cookie. |

---

## 5. Auth Controller (`controller.py`)

### File: `server/app/api/v1/auth/controller.py`

### Imports

```python
import logging                                                          # [1]
import secrets                                                          # [2]

from fastapi import APIRouter, Depends, HTTPException, Query, status    # [3]
from sqlalchemy.ext.asyncio import AsyncSession                         # [4]

from app.api.v1.auth.dto.schemas import (                               # [5]
    AuthResponse, AuthUrlResponse, LogoutRequest,
    OAuthCallbackRequest, TokenRefreshRequest, TokenResponse, UserResponse,
)
from app.api.v1.auth.jwt_guard import CurrentUser                       # [6]
from app.api.v1.auth.oauth import get_authorization_url, get_provider_config # [7]
from app.api.v1.auth.service import authenticate_oauth, refresh_access_token # [8]
from app.core.database import get_db                                    # [9]

logger = logging.getLogger(__name__)                                    # [10]

router = APIRouter(prefix="/auth", tags=["auth"])                       # [11]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Standard logging. |
| `[2]` | `secrets` module — for generating cryptographically secure random tokens (CSRF state). |
| `[3]` | FastAPI components: `APIRouter` for route grouping, `Depends` for DI, `HTTPException` for error responses, `Query` for query parameters, `status` for HTTP status codes. |
| `[4]` | Async DB session type. |
| `[5]` | Pydantic request/response schemas. |
| `[6]` | `CurrentUser` — type alias for the JWT guard dependency. Automatically validates the access token and injects `JWTPayload`. |
| `[7]` | OAuth functions for URL generation and provider validation. |
| `[8]` | Service layer functions for OAuth authentication and token refresh. |
| `[9]` | `get_db` — FastAPI dependency that yields an `AsyncSession` and handles cleanup. |
| `[10]` | Module-scoped logger. |
| `[11]` | Create a router with prefix `/auth`. All routes in this file are under `/api/v1/auth/`. Tag `"auth"` groups them in the OpenAPI docs. |

### `GET /oauth/{provider}/authorize`

```python
@router.get(                                                            # [1]
    "/oauth/{provider}/authorize",
    response_model=AuthUrlResponse,                                     # [2]
)
async def get_oauth_authorize_url(                                      # [3]
    provider: str,                                                      # [4]
    redirect_uri: str = Query(..., description="Frontend callback URL"),# [5]
):
    try:
        get_provider_config(provider)                                   # [6]
        logger.debug(f"redirect_uri: {redirect_uri}")
    except ValueError:
        raise HTTPException(                                            # [7]
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )

    state = secrets.token_urlsafe(32)                                   # [8]
    url = get_authorization_url(provider, redirect_uri, state)          # [9]

    return AuthUrlResponse(url=url, state=state)                        # [10]
```

| Line | Explanation |
|------|-------------|
| `[1]` | GET endpoint. No authentication required — this is the first step of login. |
| `[2]` | Response shape: `{ url: str, state: str }`. |
| `[3]` | Async handler. |
| `[4]` | `provider` — Path parameter from URL (e.g., `"google"`, `"kakao"`). |
| `[5]` | `redirect_uri` — Required query parameter. The frontend's callback URL (e.g., `http://localhost:3000/api/auth/callback/google`). `...` means required (no default). |
| `[6]` | Validate the provider is supported. |
| `[7]` | Return 400 for unsupported providers. |
| `[8]` | Generate a 32-byte URL-safe random string for CSRF protection. This `state` is sent to the OAuth provider, who echoes it back in the callback. |
| `[9]` | Build the full authorization URL with all OAuth parameters. |
| `[10]` | Return the URL and state to the frontend. The frontend redirects the user's browser to this URL. |

### `POST /oauth/{provider}/callback`

```python
@router.post(                                                           # [1]
    "/oauth/{provider}/callback",
    response_model=AuthResponse,                                        # [2]
)
async def oauth_callback(                                               # [3]
    provider: str,                                                      # [4]
    body: OAuthCallbackRequest,                                         # [5]
    db: AsyncSession = Depends(get_db),                                 # [6]
):
    try:
        get_provider_config(provider)                                   # [7]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )

    try:
        result = await authenticate_oauth(                              # [8]
            db, provider, body.code, body.redirect_uri
        )
    except Exception as e:
        logger.error(                                                   # [9]
            f"OAuth authentication failed for {provider}: {e}",
            exc_info=True                                               # [10]
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,                   # [11]
            detail="OAuth authentication failed. Please try again.",
        )

    return AuthResponse(**result)                                       # [12]
```

| Line | Explanation |
|------|-------------|
| `[1]` | POST endpoint — receives the authorization code from the frontend. |
| `[2]` | Response: `{ access_token, refresh_token, token_type, user }`. |
| `[3]` | Async — requires DB access for user creation. |
| `[4]` | Provider from URL path. |
| `[5]` | Request body parsed by Pydantic: `{ code: str, state: str | None, redirect_uri: str }`. FastAPI automatically validates the JSON body. |
| `[6]` | Inject a database session via dependency injection. `get_db` creates an `AsyncSession`, yields it, and handles cleanup (close/rollback) after the request. |
| `[7]` | Validate provider. |
| `[8]` | Call the service layer — this orchestrates the full OAuth flow: code exchange, profile fetch, user creation, and JWT issuance. |
| `[9]` | Log the full error for debugging. |
| `[10]` | `exc_info=True` — Include the full stack trace in the log. Essential for debugging OAuth failures (expired code, provider API changes, etc.). |
| `[11]` | Return 401 to the frontend. The frontend redirects to the sign-in page with an error message. |
| `[12]` | Unpack the result dict into an `AuthResponse`. Returns JSON to the frontend. |

### `POST /refresh`

```python
@router.post(                                                           # [1]
    "/refresh",
    response_model=TokenResponse,                                       # [2]
)
async def refresh_token(body: TokenRefreshRequest):                     # [3]
    try:
        result = refresh_access_token(body.refresh_token)               # [4]
    except ValueError as e:                                             # [5]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return TokenResponse(**result)                                      # [6]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Explicit refresh endpoint. Used when a client wants to refresh manually instead of relying on the auto-refresh middleware. |
| `[2]` | Response: `{ access_token, token_type }`. |
| `[3]` | Request body: `{ refresh_token: str }`. No authentication required — the refresh token itself is the credential. No `db` dependency — fully stateless. |
| `[4]` | Call the service's `refresh_access_token()` — decodes the refresh JWT and creates a new access token from its claims. Synchronous (no `await`). |
| `[5]` | `ValueError` is raised when the refresh token is expired or invalid. Convert to 401. |
| `[6]` | Return the new access token. |

### `POST /logout`

```python
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)         # [1]
async def logout(body: LogoutRequest):                                  # [2]
    # No-op on the server side. Client clears cookies.
    pass                                                                # [3]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Logout endpoint. Returns 204 No Content (empty response). |
| `[2]` | Request body: `{ refresh_token: str | None }`. Currently unused — included for forward compatibility if server-side revocation is added later. |
| `[3]` | **No-op** — With stateless JWT refresh tokens, there's nothing to revoke server-side. The frontend clears its cookies, and the access token expires naturally in 30 minutes. If server-side revocation is needed later, a lightweight `revoked_tokens` table can be added. |

### `GET /me`

```python
@router.get("/me", response_model=UserResponse)                        # [1]
async def get_me(current_user: CurrentUser):                            # [2]
    return UserResponse(                                                # [3]
        id=current_user.user_id,                                        # [4]
        email=current_user.email,
        name=current_user.name,
        image=None,                                                     # [5]
        role=current_user.role,
    )
```

| Line | Explanation |
|------|-------------|
| `[1]` | GET endpoint for current user info. Used by the frontend to check session status. |
| `[2]` | `CurrentUser` — FastAPI dependency that requires a valid access token. If no token or invalid token, automatically returns 401 before reaching this function. `current_user` is a `JWTPayload` with `user_id`, `email`, `name`, `role`. |
| `[3]` | Return user info as `UserResponse`. |
| `[4]` | `current_user.user_id` comes from the JWT's `sub` claim. No database lookup — all data is from the token. |
| `[5]` | `image` is `None` because the profile image URL is not stored in the JWT (too long for a header). The frontend can fetch this separately if needed. |

---

## 6. Request/Response Schemas (`dto/schemas.py`)

### File: `server/app/api/v1/auth/dto/schemas.py`

```python
class OAuthCallbackRequest(BaseModel):                                  # [1]
    code: str                                                           # [2]
    state: str | None = None                                            # [3]
    redirect_uri: str                                                   # [4]


class TokenRefreshRequest(BaseModel):                                   # [5]
    refresh_token: str                                                  # [6]


class LogoutRequest(BaseModel):                                         # [7]
    refresh_token: str | None = None                                    # [8]


class AuthResponse(BaseModel):                                          # [9]
    access_token: str                                                   # [10]
    refresh_token: str                                                  # [11]
    token_type: str = "Bearer"                                          # [12]
    user: dict                                                          # [13]


class TokenResponse(BaseModel):                                         # [14]
    access_token: str                                                   # [15]
    token_type: str = "Bearer"                                          # [16]


class AuthUrlResponse(BaseModel):                                       # [17]
    url: str                                                            # [18]
    state: str                                                          # [19]


class UserResponse(BaseModel):                                          # [20]
    id: str                                                             # [21]
    email: str | None                                                   # [22]
    name: str | None
    image: str | None
    role: str                                                           # [23]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Request body for OAuth callback. FastAPI validates the incoming JSON against this model. |
| `[2]` | `code` — The one-time authorization code from the OAuth provider. Required. |
| `[3]` | `state` — CSRF protection token echoed back by the provider. Optional because some providers may not return it. |
| `[4]` | `redirect_uri` — Must match the URI used in the authorization step. |
| `[5]` | Request body for explicit token refresh. |
| `[6]` | `refresh_token` — The JWT refresh token string. |
| `[7]` | Request body for logout. |
| `[8]` | `refresh_token` — Optional. Currently unused (no-op endpoint). |
| `[9]` | Response for successful OAuth login. |
| `[10]` | Our access JWT (30 min). |
| `[11]` | Our refresh JWT (30 days). |
| `[12]` | Standard OAuth token type. Always `"Bearer"`. |
| `[13]` | User profile: `{ id, email, name, image, role }`. Typed as `dict` for flexibility. |
| `[14]` | Response for explicit token refresh. |
| `[15]` | The newly created access JWT. |
| `[16]` | Token type — `"Bearer"`. |
| `[17]` | Response for the authorization URL generation endpoint. |
| `[18]` | The full OAuth authorization URL. Frontend redirects the browser to this URL. |
| `[19]` | CSRF state token. |
| `[20]` | Response for `GET /auth/me`. |
| `[21]` | User's database ID (CUID). |
| `[22]` | User's email. `None` if not provided by OAuth provider. |
| `[23]` | User's role — `"USER"` or `"ADMIN"`. |

---

## 7. JWT Guard (`jwt_guard.py`)

### File: `server/app/api/v1/auth/jwt_guard.py`

### JWTPayload Data Class

```python
@dataclass
class JWTPayload:                                                       # [1]
    user_id: str                                                        # [2]
    email: str | None                                                   # [3]
    name: str | None
    role: str                                                           # [4]
    exp: int | None = None                                              # [5]
    iat: int | None = None                                              # [6]

    @classmethod
    def from_dict(cls, data: dict) -> "JWTPayload":                     # [7]
        user_id = data.get("id", data.get("sub", ""))                   # [8]
        if not user_id:
            raise InvalidTokenError(                                    # [9]
                status_code=401,
                message="Invalid JWT: missing user identifier (id or sub)",
            )
        return cls(                                                     # [10]
            user_id=user_id,
            email=data.get("email"),
            name=data.get("name"),
            role=data.get("role", "USER"),
            exp=data.get("exp"),
            iat=data.get("iat"),
        )
```

| Line | Explanation |
|------|-------------|
| `[1]` | Structured representation of a decoded JWT. Using `@dataclass` for clean attribute access (e.g., `payload.user_id`). |
| `[2]` | `user_id` — Extracted from the JWT's `sub` claim. This is the user's CUID from the database. |
| `[3]` | `email`, `name` — User info from the JWT. Can be `None`. |
| `[4]` | `role` — `"USER"` or `"ADMIN"`. Used by `get_current_admin()` to enforce admin access. |
| `[5]` | `exp` — Token expiration timestamp (Unix epoch). Optional in the dataclass because it's metadata, not user data. |
| `[6]` | `iat` — Token issued-at timestamp. |
| `[7]` | Factory method to create `JWTPayload` from a raw JWT dictionary. Handles both `id` and `sub` claims for flexibility. |
| `[8]` | Try `id` first, then `sub`. Our tokens use `sub` (standard JWT claim), but `id` is supported for forward compatibility. |
| `[9]` | If neither `id` nor `sub` is present, the token is malformed. |
| `[10]` | Create the dataclass instance with all fields from the decoded JWT. Default role to `"USER"` if not present. |

### Token Extraction

```python
bearer_scheme = HTTPBearer(                                             # [1]
    scheme_name="Bearer",
    description="JWT access token",
    auto_error=False,                                                   # [2]
)

ACCESS_COOKIE_NAME = "grapoll-access-token"                             # [3]
ACCESS_COOKIE_NAME_SECURE = "__Secure-grapoll-access-token"             # [4]


async def get_token_from_header(                                        # [5]
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> str | None:
    if credentials is None:                                             # [6]
        return None
    return credentials.credentials                                      # [7]


async def get_token_from_cookie(request: Request) -> str | None:        # [8]
    for cookie_name in [ACCESS_COOKIE_NAME_SECURE, ACCESS_COOKIE_NAME]: # [9]
        token = request.cookies.get(cookie_name)                        # [10]
        if token:
            return token
    return None                                                         # [11]
```

| Line | Explanation |
|------|-------------|
| `[1]` | FastAPI security scheme — automatically parses `Authorization: Bearer <token>` header. Shows a "lock" icon in Swagger UI. |
| `[2]` | `auto_error=False` — Don't raise 401 automatically if header is missing. We handle this ourselves to support cookie fallback. |
| `[3]` | Cookie name for development (plain HTTP). |
| `[4]` | Cookie name for production (`__Secure-` prefix enforced by browsers — cookie only sent over HTTPS). |
| `[5]` | Extract token from the `Authorization` header. FastAPI dependency — injected via `Depends()`. |
| `[6]` | No `Authorization` header → return `None` (try cookies next). |
| `[7]` | Return the token string (without the `"Bearer "` prefix — already parsed by `HTTPBearer`). |
| `[8]` | Extract token from cookies. Fallback when no `Authorization` header is present (e.g., browser navigation requests). |
| `[9]` | Check `__Secure-` cookie first (production), then non-secure (development). |
| `[10]` | `request.cookies` — Dictionary of all cookies sent by the client. |
| `[11]` | No token found in cookies. |

### Token Decoding

```python
def decode_token(token: str) -> dict:                                   # [1]
    return pyjwt.decode(                                                # [2]
        token,
        settings.JWT_SECRET,                                            # [3]
        algorithms=[settings.JWT_ALGORITHM],                            # [4]
    )
```

| Line | Explanation |
|------|-------------|
| `[1]` | Decode and verify a JWT token. Used by all guard functions. |
| `[2]` | `pyjwt.decode()` — Verifies the HMAC signature (tamper detection), checks `exp` (raises `ExpiredSignatureError` if expired), and returns the decoded payload. |
| `[3]` | `JWT_SECRET` — Must match the secret used in `jwt.py` for encoding. |
| `[4]` | Explicitly specify the allowed algorithm. Prevents algorithm confusion attacks where an attacker changes the JWT header to `alg: "none"`. |

### Guard Functions

```python
async def get_current_user_optional(                                    # [1]
    request: Request,
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload | None:
    token_from_cookie = await get_token_from_cookie(request)            # [2]
    token = token_from_header or token_from_cookie                      # [3]

    if not token:                                                       # [4]
        return None

    try:
        payload = decode_token(token)                                   # [5]
        if payload.get("type") != "access":                             # [6]
            return None
        return JWTPayload.from_dict(payload)                            # [7]
    except pyjwt.ExpiredSignatureError:                                 # [8]
        logger.debug("JWT token expired (optional auth)")
        return None
    except pyjwt.InvalidTokenError as e:                                # [9]
        logger.debug(f"Invalid JWT token (optional auth): {e}")
        return None
```

| Line | Explanation |
|------|-------------|
| `[1]` | **Optional auth** — Returns `JWTPayload` or `None`. For routes that work for both logged-in and anonymous users (e.g., viewing a poll shows vote count to everyone, but shows "your vote" only to authenticated users). |
| `[2]` | Try cookies as fallback. |
| `[3]` | Prefer header over cookie. The middleware injects the refreshed token into the header, so it takes priority. |
| `[4]` | No token at all → anonymous user. Return `None`, not 401. |
| `[5]` | Decode and verify the token. |
| `[6]` | **Type check** — Reject refresh tokens. Only `type: "access"` is valid. |
| `[7]` | Token valid → return structured payload. |
| `[8]` | Expired token → treat as anonymous (no error raised). |
| `[9]` | Invalid/tampered token → treat as anonymous. |

```python
async def get_current_user(                                             # [1]
    request: Request,
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload:
    token_from_cookie = await get_token_from_cookie(request)
    token = token_from_header or token_from_cookie

    if not token:                                                       # [2]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a valid JWT token.",
            headers={"WWW-Authenticate": "Bearer"},                     # [3]
        )

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":                             # [4]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return JWTPayload.from_dict(payload)                            # [5]
    except pyjwt.ExpiredSignatureError:                                 # [6]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:                                     # [7]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

| Line | Explanation |
|------|-------------|
| `[1]` | **Required auth** — Returns `JWTPayload` or raises 401. For protected routes that require authentication. |
| `[2]` | No token → 401 Unauthorized. Unlike the optional version, this raises instead of returning `None`. |
| `[3]` | `WWW-Authenticate: Bearer` — Standard HTTP header that tells the client how to authenticate. |
| `[4]` | Reject refresh tokens used as access tokens. |
| `[5]` | Token valid → return payload. The route handler receives `current_user.user_id`, `.email`, etc. |
| `[6]` | Expired token → 401. This shouldn't happen if the middleware already refreshed the token, but handles edge cases (race conditions, middleware skip paths). |
| `[7]` | Tampered or malformed token → 401. |

```python
async def get_current_admin(                                            # [1]
    current_user: Annotated[JWTPayload, Depends(get_current_user)],     # [2]
) -> JWTPayload:
    if current_user.role != "ADMIN":                                    # [3]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,                      # [4]
            detail="Admin privileges required.",
        )
    return current_user                                                 # [5]
```

| Line | Explanation |
|------|-------------|
| `[1]` | **Admin guard** — Requires both valid token AND admin role. |
| `[2]` | Chains `get_current_user` — first validates the token (401 if invalid), then this function checks the role. |
| `[3]` | Check the `role` claim from the JWT. |
| `[4]` | 403 Forbidden (not 401) — the user is authenticated but lacks permission. |
| `[5]` | Return the same payload. The route handler has access to all user info. |

### Type Aliases

```python
CurrentUserOptional = Annotated[JWTPayload | None, Depends(get_current_user_optional)] # [1]
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]          # [2]
CurrentAdmin = Annotated[JWTPayload, Depends(get_current_admin)]        # [3]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Type alias for optional auth. Usage: `def handler(user: CurrentUserOptional)`. |
| `[2]` | Type alias for required auth. Usage: `def handler(user: CurrentUser)`. FastAPI automatically calls `get_current_user` and injects the result. |
| `[3]` | Type alias for admin auth. Usage: `def handler(admin: CurrentAdmin)`. |

---

## 8. Token Refresh Middleware (`refresh_middleware.py`)

> **Why pure ASGI, not `BaseHTTPMiddleware`?**
> Starlette's `BaseHTTPMiddleware` runs the downstream handler in a separate async task via `call_next()`. This breaks SQLAlchemy's async session greenlet context, causing `MissingGreenlet` (`f405`) errors on any endpoint that uses DB sessions. The pure ASGI approach (`__call__(scope, receive, send)`) avoids this by keeping everything in the same async context.

### File: `server/app/api/v1/auth/refresh_middleware.py`

### Constants

```python
import logging                                                          # [1]
from http.cookies import SimpleCookie                                   # [2]

import jwt as pyjwt                                                     # [3]
from starlette.types import ASGIApp, Message, Receive, Scope, Send      # [4]

from app.api.v1.auth.jwt import create_access_token, decode_refresh_token # [5]
from app.core.config import settings                                    # [6]

logger = logging.getLogger(__name__)

SKIP_PREFIXES = (                                                       # [7]
    "/api/v1/auth/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)

ACCESS_COOKIE = "grapoll-access-token"                                  # [8]
ACCESS_COOKIE_SECURE = "__Secure-grapoll-access-token"
REFRESH_COOKIE = "grapoll-refresh-token"
REFRESH_COOKIE_SECURE = "__Secure-grapoll-refresh-token"
```

| Line | Explanation |
|------|-------------|
| `[1]` | Standard logging for debug messages (e.g., "Auto-refreshed access token for user X"). |
| `[2]` | Python's `SimpleCookie` parser — used to parse the raw `Cookie` HTTP header into key-value pairs. |
| `[3]` | PyJWT for decoding tokens. Imported as `pyjwt` to avoid naming conflict with the `jwt.py` module. |
| `[4]` | ASGI types from Starlette: `ASGIApp` (next app in chain), `Message` (HTTP messages), `Receive`/`Send` (async callables for reading request/writing response), `Scope` (request metadata). |
| `[5]` | JWT functions — `create_access_token` to issue new tokens, `decode_refresh_token` to validate refresh tokens. |
| `[6]` | Settings for `JWT_SECRET` and `JWT_ALGORITHM`. |
| `[7]` | Paths to skip — auth endpoints handle their own authentication, public endpoints don't need it. |
| `[8]` | Cookie names — the middleware checks both development and production variants because it doesn't know the environment at the ASGI level. |

### Middleware Class

```python
class TokenRefreshMiddleware:                                           # [1]

    def __init__(self, app: ASGIApp) -> None:                           # [2]
        self.app = app
```

| Line | Explanation |
|------|-------------|
| `[1]` | **Pure ASGI middleware** — implements the raw ASGI interface (`__call__`) instead of inheriting from `BaseHTTPMiddleware`. This is critical: `BaseHTTPMiddleware` runs `call_next()` in a separate async task, breaking SQLAlchemy's greenlet context. |
| `[2]` | `app` is the next ASGI application in the middleware chain. The middleware wraps this app and may modify the request/response. |

### `__call__()` — Main Entry Point

```python
    async def __call__(                                                  # [1]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":                                     # [2]
            await self.app(scope, receive, send)
            return

        path = scope["path"]                                            # [3]

        if self._should_skip(path):                                     # [4]
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))                        # [5]
        cookies = self._parse_cookies(headers)                          # [6]

        access_token = self._get_access_token(headers, cookies)         # [7]
        refresh_token = self._get_refresh_token(headers, cookies)       # [8]

        new_access_token = None                                         # [9]
```

| Line | Explanation |
|------|-------------|
| `[1]` | ASGI callable interface. Every request passes through this method. `scope` = request metadata (path, headers, method), `receive` = read request body, `send` = write response. |
| `[2]` | Only handle HTTP requests. Skip WebSocket connections and lifespan events. |
| `[3]` | Extract the URL path from the ASGI scope. |
| `[4]` | Check if this path should skip token refresh (auth endpoints, docs, health). |
| `[5]` | Convert ASGI headers from `list[tuple[bytes, bytes]]` to `dict[bytes, bytes]` for easy lookup. |
| `[6]` | Parse the `Cookie` header string into a `{ name: value }` dict. |
| `[7]` | Extract access token — check `Authorization: Bearer` header first, then cookies. |
| `[8]` | Extract refresh token — check `X-Refresh-Token` header first, then cookies. |
| `[9]` | Will hold the new access token if refresh succeeds. |

### Valid Token → Pass Through

```python
        if access_token:                                                # [1]
            try:
                payload = pyjwt.decode(                                 # [2]
                    access_token,
                    settings.JWT_SECRET,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                if payload.get("type") == "access":                     # [3]
                    await self.app(scope, receive, send)                 # [4]
                    return
            except (pyjwt.ExpiredSignatureError,                        # [5]
                    pyjwt.InvalidTokenError):
                pass                                                    # [6]
```

| Line | Explanation |
|------|-------------|
| `[1]` | If an access token exists, try to validate it first. |
| `[2]` | Decode and verify the JWT — checks HMAC signature and expiration. |
| `[3]` | Verify `type == "access"`. Reject refresh tokens being used as access tokens. |
| `[4]` | **Valid token** — pass the request through unchanged. No refresh needed. |
| `[5]` | If the token is expired or invalid... |
| `[6]` | ...fall through to the refresh logic below. Don't return an error — let the refresh middleware try to fix it. |

### Attempt Refresh

```python
        if refresh_token:                                               # [1]
            try:
                refresh_payload = decode_refresh_token(refresh_token)   # [2]
                new_access_token = create_access_token(                 # [3]
                    user_id=refresh_payload["sub"],
                    email=refresh_payload.get("email"),
                    name=refresh_payload.get("name"),
                    role=refresh_payload.get("role", "USER"),
                )
                scope["headers"] = self._replace_auth_header(           # [4]
                    scope["headers"], new_access_token
                )
                logger.debug(                                           # [5]
                    "Auto-refreshed access token for user %s",
                    refresh_payload["sub"]
                )
            except (pyjwt.ExpiredSignatureError,                        # [6]
                    pyjwt.InvalidTokenError) as e:
                logger.debug("Refresh token invalid: %s", e)           # [7]
```

| Line | Explanation |
|------|-------------|
| `[1]` | If a refresh token exists, attempt to use it. |
| `[2]` | Decode the refresh JWT — validates signature, expiration, and `type == "refresh"`. **No database call** — purely in-memory JWT verification. This makes the middleware fast and stateless. |
| `[3]` | Create a new access token using the claims from the refresh token. The new token has fresh `iat` and `exp` values (another 30 minutes). |
| `[4]` | **Inject the new token into the request** — replace (or add) the `Authorization` header in the ASGI scope. The downstream route handler will see a valid access token. |
| `[5]` | Log the refresh for debugging. |
| `[6]` | If the refresh token is also expired (30+ days) or invalid (tampered)... |
| `[7]` | ...log it and fall through. The route handler's JWT guard will raise 401. |

### Inject Token into Response

```python
        if not new_access_token:                                        # [1]
            await self.app(scope, receive, send)
            return

        token_to_inject = new_access_token                              # [2]

        async def send_with_token(message: Message) -> None:            # [3]
            if message["type"] == "http.response.start":                # [4]
                headers = list(message.get("headers", []))              # [5]
                headers.append(                                         # [6]
                    (b"x-new-access-token", token_to_inject.encode())
                )
                message["headers"] = headers                            # [7]
            await send(message)                                         # [8]

        await self.app(scope, receive, send_with_token)                 # [9]
```

| Line | Explanation |
|------|-------------|
| `[1]` | If refresh failed (no refresh token or invalid), pass through unchanged. The JWT guard downstream will handle it (401). |
| `[2]` | Capture the new token for the closure. |
| `[3]` | Create a wrapper for the `send` callable. This intercepts the response before it's sent to the client. |
| `[4]` | ASGI sends responses in two parts: `http.response.start` (status code + headers) and `http.response.body` (body data). We only modify the headers part. |
| `[5]` | Get the existing response headers as a mutable list. |
| `[6]` | Append `X-New-Access-Token` header with the new JWT. The frontend reads this header and updates its cookie. |
| `[7]` | Replace the headers in the message dict. |
| `[8]` | Forward the message to the original `send` (sends to client). |
| `[9]` | Call the downstream app with the modified scope (new `Authorization` header) and our wrapped send (adds `X-New-Access-Token` to response). |

### Helper Methods

```python
    def _should_skip(self, path: str) -> bool:                          # [1]
        if path == "/":
            return True
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return True
        return False
```

| Line | Explanation |
|------|-------------|
| `[1]` | Check if the path should bypass token refresh. Root path and all `SKIP_PREFIXES` are skipped. Auth endpoints handle their own auth; public endpoints don't need it. |

```python
    def _parse_cookies(self, headers: dict[bytes, bytes]) -> dict[str, str]: # [1]
        raw = headers.get(b"cookie", b"").decode()                      # [2]
        if not raw:
            return {}
        cookie = SimpleCookie(raw)                                      # [3]
        return {k: v.value for k, v in cookie.items()}                  # [4]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Parse the raw `Cookie` header into a dictionary. |
| `[2]` | Get the `cookie` header as bytes, decode to string. Empty string if no cookies. |
| `[3]` | `SimpleCookie` — Python's built-in cookie parser. Handles URL encoding, quoted values, etc. |
| `[4]` | Convert to `{ name: value }` dict. `SimpleCookie` returns `Morsel` objects — we extract `.value`. |

```python
    def _get_access_token(                                              # [1]
        self, headers: dict[bytes, bytes], cookies: dict[str, str]
    ) -> str | None:
        auth_header = headers.get(b"authorization", b"").decode()       # [2]
        if auth_header.startswith("Bearer "):                           # [3]
            return auth_header[7:]                                      # [4]
        for name in (ACCESS_COOKIE_SECURE, ACCESS_COOKIE):              # [5]
            if name in cookies:
                return cookies[name]
        return None                                                     # [6]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Extract access token from request. |
| `[2]` | Read the `Authorization` header. |
| `[3]` | Check if it's a Bearer token. |
| `[4]` | Extract the token value — skip the `"Bearer "` prefix (7 characters). |
| `[5]` | **Fallback**: Check cookies. Try `__Secure-` cookie first (production), then plain (development). |
| `[6]` | No token found anywhere. |

```python
    def _get_refresh_token(                                             # [1]
        self, headers: dict[bytes, bytes], cookies: dict[str, str]
    ) -> str | None:
        token = headers.get(b"x-refresh-token", b"").decode()           # [2]
        if token:
            return token
        for name in (REFRESH_COOKIE_SECURE, REFRESH_COOKIE):            # [3]
            if name in cookies:
                return cookies[name]
        return None
```

| Line | Explanation |
|------|-------------|
| `[1]` | Extract refresh token from request. |
| `[2]` | Check the custom `X-Refresh-Token` header first. The frontend explicitly sends this header when making API calls. |
| `[3]` | **Fallback**: Check cookies. For browser navigation requests where the frontend can't set custom headers. |

```python
    def _replace_auth_header(                                           # [1]
        self, headers: list[tuple[bytes, bytes]], new_token: str
    ) -> list[tuple[bytes, bytes]]:
        new_headers = [                                                 # [2]
            (k, v) for k, v in headers if k.lower() != b"authorization"
        ]
        new_headers.append(                                             # [3]
            (b"authorization", f"Bearer {new_token}".encode())
        )
        return new_headers                                              # [4]
```

| Line | Explanation |
|------|-------------|
| `[1]` | Replace the `Authorization` header with a new token. Called after creating a refreshed access token. |
| `[2]` | Remove the old `Authorization` header (if any). Case-insensitive comparison. |
| `[3]` | Add the new `Authorization: Bearer <token>` header. |
| `[4]` | Return the modified header list. The ASGI scope is updated with this. |

---

## 9. Database Models

### File: `server/app/models/user.py`

```python
class Role(str, Enum):                                                  # [1]
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):                                                       # [2]
    __tablename__ = "users"                                             # [3]

    id: Mapped[str] = mapped_column(String(25), primary_key=True)       # [4]

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)# [5]
    email: Mapped[str | None] = mapped_column(                          # [6]
        String(255), nullable=True, unique=True, index=True
    )
    email_verified: Mapped[datetime | None] = mapped_column(            # [7]
        DateTime(timezone=True), nullable=True
    )
    hashed_password: Mapped[str | None] = mapped_column(                # [8]
        String(255), nullable=True
    )
    image: Mapped[str | None] = mapped_column(String(1000), nullable=True) # [9]

    role: Mapped[str] = mapped_column(                                  # [10]
        SAEnum(Role, name="Role", create_type=False),                   # [11]
        default=Role.USER,                                              # [12]
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(                       # [13]
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(                       # [14]
        DateTime(timezone=True),
        default=func.now(),                                             # [15]
        server_default=func.now(),                                      # [16]
        onupdate=func.now(),                                            # [17]
        nullable=False,
    )
```

| Line | Explanation |
|------|-------------|
| `[1]` | Role enum — `str` mixin allows comparison with string values. Values must match the PostgreSQL enum type exactly. |
| `[2]` | SQLAlchemy declarative model. `Base` provides the common ORM infrastructure. |
| `[3]` | Maps to the `users` table in PostgreSQL (created by Prisma). |
| `[4]` | Primary key — CUID string, max 25 characters. Generated by CUID2 in the auth service (not auto-generated by the DB). |
| `[5]` | Display name from OAuth provider. Nullable because some providers might not provide it. |
| `[6]` | Email — unique constraint prevents duplicate accounts. Indexed for fast lookup during account linking. |
| `[7]` | Email verification timestamp — set when the user verifies their email. Nullable. |
| `[8]` | Hashed password — for future email/password auth. Not used with OAuth (always `None`). |
| `[9]` | Profile image URL from OAuth provider. `String(1000)` because Google profile picture URLs can be very long. |
| `[10]` | User role column. |
| `[11]` | `SAEnum(Role, name="Role", create_type=False)` — Maps to PostgreSQL's custom enum type `"Role"` (created by Prisma). `create_type=False` is critical: without it, SQLAlchemy tries to create the enum type on startup, which fails because it already exists. The `name="Role"` must match the exact PostgreSQL type name (case-sensitive). |
| `[12]` | `default=Role.USER` — Python-side default. New users are `USER` unless explicitly set to `ADMIN`. |
| `[13]` | `created_at` — `server_default=func.now()` translates to `DEFAULT NOW()` in SQL. Set once when the row is inserted. |
| `[14]` | `updated_at` — Auto-updates on every modification. |
| `[15]` | `default=func.now()` — Python-side (client) default. Needed because the Prisma-created table may not have a DB-level default for this column. Without this, SQLAlchemy would insert `NULL` and PostgreSQL would reject it (NOT NULL constraint). |
| `[16]` | `server_default=func.now()` — DB-level default (`DEFAULT NOW()` in SQL). Used when inserting via raw SQL. |
| `[17]` | `onupdate=func.now()` — SQLAlchemy automatically sets this to `NOW()` on every UPDATE. Tracks when the row was last modified. |

### File: `server/app/models/account.py`

```python
class Account(Base):                                                    # [1]
    __tablename__ = "accounts"                                          # [2]

    id: Mapped[str] = mapped_column(String(25), primary_key=True)       # [3]

    user_id: Mapped[str] = mapped_column(                               # [4]
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),                     # [5]
        nullable=False,
    )

    type: Mapped[str] = mapped_column(String(255), nullable=False)      # [6]
    provider: Mapped[str] = mapped_column(String(255), nullable=False)  # [7]
    provider_account_id: Mapped[str] = mapped_column(                   # [8]
        String(255), nullable=False
    )

    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True) # [9]
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # [10]
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True) # [11]
    token_type: Mapped[str | None] = mapped_column(String(255), nullable=True) # [12]
    scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # [13]
    session_state: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="accounts") # [14]

    __table_args__ = (                                                  # [15]
        UniqueConstraint(
            "provider", "provider_account_id",
            name="uq_accounts_provider_account"
        ),
    )
```

| Line | Explanation |
|------|-------------|
| `[1]` | Account model — stores OAuth provider credentials linked to users. One user can have multiple accounts (Google + Kakao). |
| `[2]` | Maps to the `accounts` table (created by Prisma). |
| `[3]` | Primary key — CUID generated by the auth service. |
| `[4]` | Foreign key to `users.id`. |
| `[5]` | `ondelete="CASCADE"` — When a user is deleted, all their accounts are automatically deleted. |
| `[6]` | `type` — Always `"oauth"` for OAuth logins. Supports future auth types (e.g., `"credentials"`). |
| `[7]` | `provider` — OAuth provider name: `"google"` or `"kakao"`. |
| `[8]` | `provider_account_id` — The provider's unique user ID (e.g., Google's `sub`, Kakao's `id`). Used to look up existing users on login. |
| `[9]` | Provider's refresh token. `Text` because tokens can be very long. Stored for future provider API calls. |
| `[10]` | Provider's access token. Updated on every login. |
| `[11]` | Provider token expiration as Unix timestamp. |
| `[12]` | Token type (usually `"Bearer"`). |
| `[13]` | OpenID Connect ID token (JWT). Contains user claims from the provider. |
| `[14]` | Bidirectional relationship — `account.user` returns the `User` model, `user.accounts` returns all linked accounts. |
| `[15]` | Unique constraint — prevents the same provider+account_id combination from being linked to multiple users. |

---

## 10. Application Entry Point and Middleware Stack (`main.py`)

### File: `server/app/main.py`

### CORS Configuration

```python
_cors_origins = [str(settings.FRONTEND_URL).rstrip("/")]                # [1]
if settings.DEBUG:                                                      # [2]
    _cors_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(                                                      # [3]
    CORSMiddleware,
    allow_origins=_cors_origins,                                        # [4]
    allow_credentials=True,                                             # [5]
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], # [6]
    allow_headers=[                                                     # [7]
        "Content-Type", "Authorization", "Cookie", "X-Refresh-Token"
    ],
    expose_headers=["X-New-Access-Token"],                              # [8]
)
```

| Line | Explanation |
|------|-------------|
| `[1]` | Build the list of allowed CORS origins. Production uses the configured `FRONTEND_URL`. |
| `[2]` | In debug mode, also allow `localhost:3000` and `127.0.0.1:3000` (Next.js dev server). |
| `[3]` | Register CORS middleware. Required because the frontend (port 3000) and backend (port 8000) are on different origins. |
| `[4]` | `allow_origins` — Only requests from these origins are allowed. Prevents cross-site request forgery from malicious sites. |
| `[5]` | `allow_credentials=True` — Allow cookies to be sent cross-origin. Required for httpOnly cookie authentication. |
| `[6]` | Allowed HTTP methods. |
| `[7]` | `allow_headers` — Custom headers the frontend is allowed to send. `X-Refresh-Token` is our custom header for sending the refresh token. Without this, the browser blocks the header. |
| `[8]` | `expose_headers` — Custom response headers that the browser JavaScript is allowed to read. By default, CORS only exposes standard headers. `X-New-Access-Token` must be exposed so the frontend can read it with `res.headers.get("x-new-access-token")`. |

### Middleware Stack

```python
app.add_middleware(CORSMiddleware, ...)                                  # [1]
app.add_middleware(TokenRefreshMiddleware)                               # [2]
app.add_middleware(SlowAPIMiddleware)                                    # [3]

@app.middleware("http")                                                  # [4]
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

| Line | Explanation |
|------|-------------|
| `[1]` | CORS middleware — first in the chain. Handles preflight `OPTIONS` requests and adds `Access-Control-*` headers to responses. |
| `[2]` | Token refresh middleware — auto-refreshes expired access tokens. Runs after CORS (so CORS headers are already set). |
| `[3]` | Rate limiting middleware — `SlowAPI` throttles requests per IP (default: 60/min). |
| `[4]` | Request ID middleware — attaches a unique ID to every request for tracing and debugging. |

**Execution order per request** (Starlette processes middleware in reverse order of `add_middleware` calls):

```
Request → CORS → TokenRefresh → RateLimit → RequestID → Route Handler
         ↓         ↓               ↓            ↓            ↓
    preflight   refresh if     rate check    attach ID    business
    + headers   token expired                            logic
```

---

## Security Considerations

| Concern | Protection |
|---------|------------|
| **Token type misuse** | `"type"` claim (`"access"` vs `"refresh"`) prevents refresh tokens from being used as access tokens. `jwt_guard.py` rejects `type != "access"`. |
| **Same signing secret** | Both tokens use `JWT_SECRET`. Acceptable because the `type` claim prevents misuse. |
| **No server-side revocation** | Logout is client-side only (cookies cleared). Access token expires in 30 min. If revocation is needed, add a `revoked_tokens` table. |
| **Cookie security** | Production: `__Secure-` prefix, `httpOnly`, `secure`, `sameSite: lax`. |
| **Algorithm confusion** | `jwt.decode()` explicitly specifies `algorithms=["HS256"]` to prevent `alg: "none"` attacks. |
| **Stateless middleware** | Zero DB calls — fast, scalable, no bottleneck. |
| **Pure ASGI middleware** | Avoids `BaseHTTPMiddleware` which breaks SQLAlchemy async session greenlet context (`f405`). |
| **CORS** | `allow_credentials=True` with explicit `allow_origins` (no wildcards). Custom headers explicitly listed. |
