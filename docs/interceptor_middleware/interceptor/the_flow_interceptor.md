# The Interceptor Flow in Grapoll

## Overview

Grapoll uses three interceptors (auth guards) implemented as FastAPI dependencies in `app/api/v1/auth/jwt_guard.py`:

| Interceptor | Type | Behavior |
|---|---|---|
| `CurrentUserOptional` | `JWTPayload \| None` | Returns `None` if no token — endpoint runs for anonymous users |
| `CurrentUser` | `JWTPayload` | Raises 401 if no valid token — endpoint requires authentication |
| `CurrentAdmin` | `JWTPayload` | Raises 403 if not admin — endpoint requires admin role |

---

## Dependency Resolution Chain

```
HTTPBearer (FastAPI built-in)
    │
    ▼
get_token_from_header()          ← extracts token from Authorization header
    │
    ▼
get_token_from_cookie()          ← fallback: extracts token from cookie
    │
    ▼
get_current_user()               ← decodes JWT, validates type="access"
    │                               raises 401 if invalid
    ▼
get_current_admin()              ← checks role == "ADMIN"
                                    raises 403 if not admin
```

---

## Step-by-Step Flow

### Example: `POST /api/v1/posts` (requires `CurrentUser`)

```python
# app/api/v1/post/controller.py
@router.post("", response_model=PostResponse, status_code=201)
async def create_post(
    data: PostCreate,
    current_user: CurrentUser,  # ← triggers the interceptor chain
    postService: Annotated[PostService, Depends(get_post_service)],
):
```

FastAPI sees `CurrentUser` which is:

```python
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]
```

### Step 1: Token Extraction from Header

```python
# jwt_guard.py
bearer_scheme = HTTPBearer(scheme_name="Bearer", auto_error=False)

async def get_token_from_header(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    if credentials is None:
        return None
    return credentials.credentials
    # "Authorization: Bearer eyJ..." → returns "eyJ..."
```

`HTTPBearer` is FastAPI's built-in dependency. It parses the `Authorization` header and returns `HTTPAuthorizationCredentials(scheme="Bearer", credentials="eyJ...")`. If no header exists, `auto_error=False` makes it return `None` instead of raising 403.

### Step 2: Token Extraction from Cookie (Fallback)

```python
# jwt_guard.py
ACCESS_COOKIE_NAME = "grapoll-access-token"
ACCESS_COOKIE_NAME_SECURE = "__Secure-grapoll-access-token"

async def get_token_from_cookie(request: Request) -> str | None:
    for cookie_name in [ACCESS_COOKIE_NAME_SECURE, ACCESS_COOKIE_NAME]:
        token = request.cookies.get(cookie_name)
        if token:
            return token
    return None
```

Checks both cookie names (production uses `__Secure-` prefix).

### Step 3: Token Validation (`get_current_user`)

```python
# jwt_guard.py
async def get_current_user(
    request: Request,
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload:
    # Fallback to cookie if no header
    token_from_cookie = await get_token_from_cookie(request)
    token = token_from_header or token_from_cookie

    # No token at all → 401
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a valid JWT token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode JWT: verify signature + check expiration
        payload = decode_token(token)

        # Reject refresh tokens used as access tokens
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )

        # Convert dict → structured JWTPayload dataclass
        return JWTPayload.from_dict(payload)

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your token.",
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token. Please log in again.",
        )
```

### Step 4: JWTPayload Injection

If validation succeeds, `get_current_user` returns a `JWTPayload` dataclass:

```python
@dataclass
class JWTPayload:
    user_id: str        # from payload["sub"]
    email: str | None   # from payload["email"]
    name: str | None    # from payload["name"]
    role: str           # from payload["role"]
    exp: int | None     # expiration timestamp
    iat: int | None     # issued at timestamp
```

FastAPI injects this into the endpoint's `current_user` parameter. The endpoint uses `current_user.user_id` to identify who is making the request.

---

## Optional Auth Flow (`CurrentUserOptional`)

```python
# jwt_guard.py
async def get_current_user_optional(
    request: Request,
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload | None:
    token_from_cookie = await get_token_from_cookie(request)
    token = token_from_header or token_from_cookie

    if not token:
        return None  # ← returns None instead of raising 401

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None  # ← returns None instead of raising 401
        return JWTPayload.from_dict(payload)
    except pyjwt.ExpiredSignatureError:
        return None  # ← returns None instead of raising 401
    except pyjwt.InvalidTokenError:
        return None  # ← returns None instead of raising 401
```

The key difference: every error path returns `None` instead of raising `HTTPException`. The endpoint always runs.

```python
@router.get("/polls")
async def get_polls(user: CurrentUserOptional):
    if user:
        # Logged in — show "you voted" badges
        pass
    else:
        # Anonymous — show public view
        pass
```

---

## Admin Auth Flow (`CurrentAdmin`)

```python
# jwt_guard.py
async def get_current_admin(
    current_user: Annotated[JWTPayload, Depends(get_current_user)],
) -> JWTPayload:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user
```

This chains on `get_current_user` — so it first validates the token (401 if invalid), then checks the role (403 if not admin).

---

## Exception Flow Summary

```
                        No token     Expired token   Invalid token    Valid, not admin   Valid admin
                        ────────     ─────────────   ─────────────    ────────────────   ──────────

CurrentUserOptional     None         None            None             N/A                JWTPayload
                        (no error)   (no error)      (no error)                          (no error)

CurrentUser             401          401             401              N/A                JWTPayload
                        HTTPException HTTPException  HTTPException                       (no error)

CurrentAdmin            401          401             401              403                JWTPayload
                        (from        (from           (from            HTTPException      (no error)
                        get_current  get_current     get_current      (from
                        _user)       _user)          _user)           get_current_admin)
```

---

## Token Extraction Priority

The interceptor checks two sources for the access token:

```
1. Authorization: Bearer <token>  ← header (priority)
2. grapoll-access-token cookie    ← cookie (fallback)
```

Header takes priority (`token_from_header or token_from_cookie`). This supports both:
- **Server-to-server calls** — token in Authorization header (e.g., Next.js → FastAPI)
- **Browser direct calls** — token in httpOnly cookie (if browser calls FastAPI directly)

---

## Related Files

| File | Role |
|------|------|
| `app/api/v1/auth/jwt_guard.py` | All three interceptors + JWTPayload dataclass |
| `app/api/v1/auth/jwt.py` | `decode_access_token()` — JWT decode logic |
| `app/api/v1/interpreter/__init__.py` | Re-exports interceptors for convenience |
| `app/core/config.py` | `JWT_SECRET`, `JWT_ALGORITHM` |
