# How to Implement Middleware in FastAPI

## What is Middleware?

Middleware is a function or class that processes **every HTTP request** before it reaches the endpoint, and **every response** before it's sent back to the client. It wraps the entire application at the ASGI level.

---

## Three Ways to Create Middleware

### 1. `@app.middleware("http")` Decorator (Simplest)

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)  # pass to next layer
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

- Receives a parsed `Request` object and `call_next` function
- `call_next(request)` passes the request to the next middleware or endpoint
- You can run code before (pre-processing) and after (post-processing) `call_next`
- Under the hood, this uses `BaseHTTPMiddleware`

**Use for:** Quick prototyping, simple use cases.

### 2. `BaseHTTPMiddleware` Class (Reusable)

```python
from starlette.middleware.base import BaseHTTPMiddleware

class CustomHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_value="Example"):
        super().__init__(app)
        self.header_value = header_value

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Custom"] = self.header_value
        return response

app.add_middleware(CustomHeaderMiddleware, header_value="MyValue")
```

- Subclass `BaseHTTPMiddleware` and implement `dispatch()`
- Accepts constructor arguments for configuration
- Same `Request`/`Response` interface as the decorator approach

**Limitations:**
- **Performance**: creates 7 intermediate objects per request, up to 5x throughput loss
- **`contextvars` broken**: changes in dependencies/endpoints don't propagate back to middleware
- **Async context**: runs the endpoint in a separate async task, which breaks SQLAlchemy async sessions (`MissingGreenlet` error)

### 3. Pure ASGI Middleware (Best Performance)

```python
from starlette.types import ASGIApp, Message, Scope, Receive, Send

class PureASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Pre-processing: modify scope (request) before it reaches the endpoint
        # ...

        # To modify the response, wrap the send function:
        async def custom_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-custom", b"value"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, custom_send)

app.add_middleware(PureASGIMiddleware)
```

- Operates on raw ASGI primitives: `scope` (dict), `receive` (async callable), `send` (async callable)
- No `Request`/`Response` objects — you work with raw bytes and dicts
- Headers are `list[tuple[bytes, bytes]]`, not a dict
- Best performance, no context issues, no async task separation

**Use for:** Production middleware, anything that needs `contextvars`, or when using SQLAlchemy async sessions.

---

## Comparison

| Aspect | `@app.middleware` | `BaseHTTPMiddleware` | Pure ASGI |
|---|---|---|---|
| Complexity | Lowest | Low | Highest |
| Performance | Poor | Poor | Best |
| `contextvars` | Broken | Broken | Works |
| SQLAlchemy async | Breaks | Breaks | Works |
| Request access | `Request` object | `Request` object | Raw `scope` dict |
| Response access | `Response` object | `Response` object | Wrap `send()` |
| Best for | Prototyping | Reusable, non-critical | Production |

---

## Middleware Execution Order

Middleware registered with `add_middleware` executes in **reverse registration order** (LIFO):

```python
app.add_middleware(MiddlewareA)  # registered first  → innermost
app.add_middleware(MiddlewareB)  # registered second → outermost
```

Request path:  `Client → MiddlewareB → MiddlewareA → Endpoint`
Response path: `Endpoint → MiddlewareA → MiddlewareB → Client`

The **last registered middleware runs first** on incoming requests.

---

## ASGI Concepts

### Scope

A dict describing the connection:

```python
scope = {
    "type": "http",            # "http" or "websocket"
    "path": "/api/v1/posts",
    "method": "POST",
    "headers": [
        (b"authorization", b"Bearer eyJ..."),
        (b"content-type", b"application/json"),
    ],
    "query_string": b"sort=popular",
}
```

### Receive

An async function that returns the request body:

```python
message = await receive()
# message = {"type": "http.request", "body": b'{"title": "..."}'}
```

### Send

An async function that sends the response (called twice):

```python
# First call: status code + headers
await send({
    "type": "http.response.start",
    "status": 200,
    "headers": [(b"content-type", b"application/json")],
})

# Second call: body
await send({
    "type": "http.response.body",
    "body": b'{"id": "123"}',
})
```

### Wrapping `send()` to Modify Responses

Since `send()` is called by the inner app (not by the middleware), you need to **wrap** it to intercept response data:

```python
async def __call__(self, scope, receive, send):
    async def modified_send(message):
        if message["type"] == "http.response.start":
            # Add or modify response headers here
            headers = list(message.get("headers", []))
            headers.append((b"x-custom", b"value"))
            message["headers"] = headers
        await send(message)  # forward to outer layer

    await self.app(scope, receive, modified_send)
```

### Short-Circuiting (Returning Early)

To return a response without calling the inner app:

```python
async def __call__(self, scope, receive, send):
    if should_block(scope):
        response = JSONResponse({"detail": "Blocked"}, status_code=403)
        await response(scope, receive, send)
        return  # don't call self.app

    await self.app(scope, receive, send)
```

---

## References

- [FastAPI — Middleware Tutorial](https://fastapi.tiangolo.com/tutorial/middleware/)
- [FastAPI — Advanced Middleware](https://fastapi.tiangolo.com/advanced/middleware/)
- [FastAPI — CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [Starlette — Middleware](https://www.starlette.io/middleware/)
