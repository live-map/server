# How to Implement an Interceptor in FastAPI

## What is an Interceptor in FastAPI?

FastAPI doesn't have a built-in concept called "interceptor". Instead, it uses **dependency injection via `Depends()`** to achieve the same pattern. A dependency function runs before the endpoint, can extract data from the request, validate it, and reject the request by raising `HTTPException`.

This is documented in FastAPI's official docs under [Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) and [Security](https://fastapi.tiangolo.com/tutorial/security/).

---

## Basic Pattern

### 1. Create a dependency function

A dependency is any callable (function or class) that FastAPI can call:

```python
from fastapi import Depends, HTTPException, status

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "expected-key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key
```

### 2. Declare it on an endpoint

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/protected")
async def protected_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "You have access", "key": api_key}
```

FastAPI will:
1. See `Depends(verify_api_key)` in the function signature
2. Call `verify_api_key()` before the endpoint runs
3. Resolve its parameters from the request (header `X-Api-Key`)
4. If it raises `HTTPException` → return error response, endpoint never runs
5. If it returns a value → inject that value into `api_key`

---

## Using `Annotated` Type Aliases

To avoid repeating `Depends(...)` on every endpoint, create a reusable type alias:

```python
from typing import Annotated
from fastapi import Depends

# Define once
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]

# Use everywhere — clean, no repetition
@app.get("/me")
async def get_me(user: CurrentUser):
    return user

@app.post("/posts")
async def create_post(user: CurrentUser, data: PostCreate):
    ...
```

This is how Grapoll defines its auth guards in `jwt_guard.py`:

```python
CurrentUserOptional = Annotated[JWTPayload | None, Depends(get_current_user_optional)]
CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]
CurrentAdmin = Annotated[JWTPayload, Depends(get_current_admin)]
```

---

## Chaining Dependencies (Sub-Dependencies)

Dependencies can depend on other dependencies, forming a chain that FastAPI resolves automatically:

```python
# Level 1: Extract token from header
oauth2_scheme = HTTPBearer(auto_error=False)

async def get_token_from_header(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(oauth2_scheme)],
) -> str | None:
    if credentials is None:
        return None
    return credentials.credentials

# Level 2: Decode token → return user payload
async def get_current_user(
    token_from_header: Annotated[str | None, Depends(get_token_from_header)],
) -> JWTPayload:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    return JWTPayload.from_dict(payload)

# Level 3: Check admin role
async def get_current_admin(
    current_user: Annotated[JWTPayload, Depends(get_current_user)],
) -> JWTPayload:
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
```

Resolution graph when an endpoint uses `CurrentAdmin`:

```
get_token_from_header()        ← extracts Bearer token
    ↓
get_current_user()             ← decodes JWT, raises 401 if invalid
    ↓
get_current_admin()            ← checks role, raises 403 if not admin
    ↓
endpoint()                     ← receives validated admin JWTPayload
```

If any dependency in the chain raises `HTTPException`, the entire chain short-circuits. The endpoint never runs.

---

## Using `Depends()` on a Class

When you pass a class to `Depends()`, FastAPI calls the class constructor (`__init__`), and the constructor's parameters are resolved from the request or from other dependencies:

```python
class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)) -> None:
        self.repo = AuthRepository(db)

# On the endpoint:
@router.post("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    service: AuthService = Depends(),  # Depends() with no argument = Depends(AuthService)
):
    result = await service.authenticate_oauth(provider, body.code, body.redirect_uri)
```

`Depends()` with no argument is shorthand for `Depends(AuthService)` — FastAPI infers the class from the type annotation.

---

## Guard-Only Dependencies (No Return Value Needed)

If you only need a dependency to validate/guard but don't need its return value, use `dependencies=[]` on the decorator:

```python
async def verify_token(x_token: str = Header(...)):
    if x_token != "expected":
        raise HTTPException(status_code=400, detail="Invalid token")

# Return value is discarded — purely a guard
@app.get("/items/", dependencies=[Depends(verify_token)])
async def read_items():
    return [{"item": "Foo"}]
```

---

## Three Auth Levels in Grapoll

```python
# 1. No auth — fully public
@router.get("/health")
async def health_check():
    return {"status": "healthy"}

# 2. Optional auth — works for both anonymous and logged-in
@router.get("/polls")
async def get_polls(user: CurrentUserOptional):
    if user:
        # show personalized data
    else:
        # show public data

# 3. Required auth — 401 if not logged in
@router.post("/posts")
async def create_post(user: CurrentUser):
    # user is guaranteed to be a valid JWTPayload

# 4. Admin only — 403 if not admin
@router.delete("/users/{id}")
async def delete_user(user: CurrentAdmin):
    # user is guaranteed to be admin
```

---

## Key Rules

1. **Pass the function reference**, not the call: `Depends(get_current_user)` not `Depends(get_current_user())`
2. **Raise `HTTPException`** to reject — don't return error values
3. **Dependencies are cached per request** — if two endpoints in the same request depend on `get_current_user`, it's called once
4. **Use `Annotated` type aliases** to avoid repetition across endpoints
5. **Dependencies appear in OpenAPI docs** — FastAPI auto-generates the lock icon and security schemes in Swagger UI

---

## References

- [FastAPI — Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI — Sub-dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/)
- [FastAPI — Security First Steps](https://fastapi.tiangolo.com/tutorial/security/first-steps/)
- [FastAPI — Get Current User](https://fastapi.tiangolo.com/tutorial/security/get-current-user/)
- [FastAPI — Dependencies in Path Operation Decorators](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/)
