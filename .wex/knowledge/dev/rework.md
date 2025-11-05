# Architecture Rework Proposal

## Current State Analysis

The `AbstractGateway` class currently serves as the foundation for API client implementations. While functional, it exhibits several architectural issues that limit its extensibility, testability, and maintainability.

### Core Issues

#### 1. Single Responsibility Principle Violation

The class handles multiple concerns simultaneously:
- HTTP client operations (requests wrapper)
- Rate limiting
- Error handling and tracking
- Logging and display
- Connection state management
- Response parsing and formatting

**Impact**: Difficult to test individual behaviors, hard to extend without modifying the base class, increased coupling.

#### 2. Tight Coupling with `requests` Library

```python
def make_request(...) -> requests.Response | None:
```

**Problems**:
- Cannot use alternative HTTP clients (`httpx`, `aiohttp`)
- No native async/await support
- Exposes implementation details through return type
- Difficult to mock for testing

#### 3. Inconsistent API Design

```python
# Mixed language conventions
check_connexion()  # French
check_status_code()  # English
connected: bool  # English

# Unclear method semantics
check_connexion() -> bool  # What does it check?
connect() -> bool  # Does nothing concrete
```

#### 4. Confusing Status Code Handling

```python
# Three different behaviors:
expected_status_codes=None  # Accepts ANY status code (dangerous)
expected_status_codes=200   # Validates single code
expected_status_codes=[200, 201]  # Validates multiple codes
```

**Problem**: Default behavior (`None`) accepts all responses, including server errors (500, 503), treating them as successful.

#### 5. Problematic Mutable State

```python
last_exception: Any  # Should be Exception | None
last_request_time: float | None
connected: bool  # Global state, thread-unsafe
```

**Impact**: Not thread-safe, difficult to reason about, hidden side effects.

#### 6. Fragile Content-Type Logic

Lines 188-220 contain complex conditional logic for determining how to send request data based on Content-Type headers. This is error-prone and difficult to extend.

#### 7. Missing Retry Logic

No built-in support for automatic retries on transient failures (429, 503, timeouts).

#### 8. No Async Support

Modern applications increasingly require async HTTP operations for performance and scalability.

---

## Proposed Architecture

### Design Principles

1. **Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Dependency Inversion**: Depend on abstractions, not concrete implementations
3. **Composability**: Behaviors can be combined through middleware pattern
4. **Immutability**: Request/Response objects are immutable for thread safety
5. **Type Safety**: Strong typing without `Any` types
6. **Testability**: Easy to mock and test in isolation

### Module Structure

```
wexample_api/
├── client/
│   ├── base_client.py          # Abstract HTTP client interface
│   ├── sync_client.py          # Synchronous implementation (requests)
│   └── async_client.py         # Asynchronous implementation (httpx)
├── middleware/
│   ├── base.py                 # Middleware interface
│   ├── rate_limiter.py         # Rate limiting middleware
│   ├── retry.py                # Retry logic middleware
│   ├── logger.py               # Logging middleware
│   └── error_handler.py        # Error handling middleware
├── models/
│   ├── request.py              # HttpRequest (immutable dataclass)
│   └── response.py             # HttpResponse (immutable wrapper)
└── gateway.py                  # Gateway orchestrator
```

### Core Components

#### 1. Immutable Request/Response Models

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class HttpRequest:
    """Immutable HTTP request representation."""
    url: str
    method: HttpMethod
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, Any] | None = None
    body: Any = None
    timeout: float = 30.0
    
    def with_header(self, key: str, value: str) -> HttpRequest:
        """Return new request with added header."""
        return dataclasses.replace(
            self, 
            headers={**self.headers, key: value}
        )


@dataclass(frozen=True)
class HttpResponse:
    """Immutable HTTP response wrapper."""
    status_code: int
    headers: dict[str, str]
    body: bytes
    request: HttpRequest
    
    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300
    
    def json(self) -> Any:
        import json
        return json.loads(self.body.decode())
    
    @property
    def text(self) -> str:
        return self.body.decode()
```

**Benefits**:
- Thread-safe by design
- No hidden mutations
- Clear data flow
- Easy to test

#### 2. Abstract HTTP Client Interface

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T', bound='HttpResponse')

class HttpClient(ABC, Generic[T]):
    """Abstract HTTP client interface."""
    
    @abstractmethod
    def execute(self, request: HttpRequest) -> T:
        """Execute HTTP request and return response."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close client and cleanup resources."""
        pass
```

**Benefits**:
- Decouples from specific HTTP library
- Enables multiple implementations (sync/async)
- Easy to mock for testing
- Future-proof for library changes

#### 3. Concrete Client Implementations

```python
class RequestsClient(HttpClient[HttpResponse]):
    """Synchronous implementation using requests library."""
    
    def execute(self, request: HttpRequest) -> HttpResponse:
        import requests
        
        response = requests.request(
            method=request.method.value,
            url=request.url,
            headers=request.headers,
            params=request.query_params,
            json=request.body if isinstance(request.body, dict) else None,
            data=request.body if not isinstance(request.body, dict) else None,
            timeout=request.timeout,
        )
        
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
            request=request,
        )
    
    def close(self) -> None:
        pass  # requests handles session cleanup


class HttpxAsyncClient(HttpClient[HttpResponse]):
    """Asynchronous implementation using httpx library."""
    
    async def execute(self, request: HttpRequest) -> HttpResponse:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method.value,
                url=request.url,
                headers=request.headers,
                params=request.query_params,
                json=request.body,
                timeout=request.timeout,
            )
            
            return HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.content,
                request=request,
            )
    
    async def close(self) -> None:
        pass
```

#### 4. Middleware Pattern

```python
class Middleware(ABC):
    """Base middleware for request/response processing."""
    
    @abstractmethod
    def process_request(self, request: HttpRequest) -> HttpRequest:
        """Process request before sending."""
        return request
    
    @abstractmethod
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        """Process response after receiving."""
        return response
```

**Example Middlewares**:

```python
class RateLimitMiddleware(Middleware):
    """Rate limiting middleware."""
    
    def __init__(self, min_delay: float = 1.0):
        self._min_delay = min_delay
        self._last_request: float | None = None
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        import time
        
        if self._last_request is not None:
            elapsed = time.time() - self._last_request
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)
        
        self._last_request = time.time()
        return request
    
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        return response


class LoggingMiddleware(Middleware):
    """Logging middleware using IoManager."""
    
    def __init__(self, io_manager, quiet: bool = False):
        self._io = io_manager
        self._quiet = quiet
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        if not self._quiet:
            self._io.debug(
                f"{request.method.value} -> {request.url}",
                symbol="🌍"
            )
        return request
    
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        if not self._quiet:
            self._io.debug(
                f"{request.method.value} | {response.status_code} -> {request.url}",
                symbol="✓" if response.is_success else "✗"
            )
        return response


class RetryMiddleware(Middleware):
    """Retry middleware for transient failures."""
    
    def __init__(
        self, 
        max_retries: int = 3,
        retry_on: set[int] = {429, 500, 502, 503, 504},
        backoff_factor: float = 2.0
    ):
        self._max_retries = max_retries
        self._retry_on = retry_on
        self._backoff_factor = backoff_factor
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        return request
    
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        # Note: Actual retry logic would be implemented at Gateway level
        # This middleware marks responses that should be retried
        return response


class AuthMiddleware(Middleware):
    """Authentication middleware."""
    
    def __init__(self, token: str):
        self._token = token
    
    def process_request(self, request: HttpRequest) -> HttpRequest:
        return request.with_header("Authorization", f"Bearer {self._token}")
    
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        return response
```

#### 5. Gateway Orchestrator

```python
class ApiGateway:
    """
    Modern API Gateway with composable middleware.
    
    Example:
        gateway = ApiGateway(
            base_url="https://api.example.com",
            client=RequestsClient(),
        )
        gateway.add_middleware(RateLimitMiddleware(min_delay=1.0))
        gateway.add_middleware(LoggingMiddleware(io_manager))
        
        request = HttpRequest(
            url="/users/1",
            method=HttpMethod.GET,
        )
        response = gateway.execute(request)
    """
    
    def __init__(
        self,
        base_url: str,
        client: HttpClient,
        default_headers: dict[str, str] | None = None,
    ):
        self._base_url = base_url.rstrip('/')
        self._client = client
        self._default_headers = default_headers or {}
        self._middlewares: list[Middleware] = []
    
    def add_middleware(self, middleware: Middleware) -> None:
        """Add middleware to the processing pipeline."""
        self._middlewares.append(middleware)
    
    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute request through middleware pipeline."""
        # Build full URL
        if not request.url.startswith('http'):
            url = f"{self._base_url}/{request.url.lstrip('/')}"
            request = dataclasses.replace(request, url=url)
        
        # Add default headers
        for key, value in self._default_headers.items():
            if key not in request.headers:
                request = request.with_header(key, value)
        
        # Process request through middlewares
        for middleware in self._middlewares:
            request = middleware.process_request(request)
        
        # Execute request
        response = self._client.execute(request)
        
        # Process response through middlewares (reverse order)
        for middleware in reversed(self._middlewares):
            response = middleware.process_response(request, response)
        
        return response
    
    # Convenience methods
    def get(self, endpoint: str, **kwargs) -> HttpResponse:
        """Convenience GET method."""
        return self.execute(
            HttpRequest(url=endpoint, method=HttpMethod.GET, **kwargs)
        )
    
    def post(self, endpoint: str, body: Any = None, **kwargs) -> HttpResponse:
        """Convenience POST method."""
        return self.execute(
            HttpRequest(
                url=endpoint, 
                method=HttpMethod.POST, 
                body=body,
                **kwargs
            )
        )
    
    def put(self, endpoint: str, body: Any = None, **kwargs) -> HttpResponse:
        """Convenience PUT method."""
        return self.execute(
            HttpRequest(
                url=endpoint, 
                method=HttpMethod.PUT, 
                body=body,
                **kwargs
            )
        )
    
    def delete(self, endpoint: str, **kwargs) -> HttpResponse:
        """Convenience DELETE method."""
        return self.execute(
            HttpRequest(url=endpoint, method=HttpMethod.DELETE, **kwargs)
        )
    
    def close(self) -> None:
        """Close gateway and cleanup resources."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
```

### Usage Example

```python
from wexample_prompt.common.io_manager import IoManager
from wexample_api.client.sync_client import RequestsClient
from wexample_api.gateway import ApiGateway
from wexample_api.middleware.rate_limiter import RateLimitMiddleware
from wexample_api.middleware.logger import LoggingMiddleware
from wexample_api.middleware.retry import RetryMiddleware
from wexample_api.middleware.auth import AuthMiddleware
from wexample_api.models.request import HttpRequest
from wexample_api.enums.http import HttpMethod

# Setup
io_manager = IoManager()
gateway = ApiGateway(
    base_url="https://api.example.com",
    client=RequestsClient(),
    default_headers={"User-Agent": "MyApp/1.0"}
)

# Compose middleware pipeline
gateway.add_middleware(AuthMiddleware(token="secret-token"))
gateway.add_middleware(RateLimitMiddleware(min_delay=0.5))
gateway.add_middleware(RetryMiddleware(max_retries=3))
gateway.add_middleware(LoggingMiddleware(io_manager, quiet=False))

# Make requests
response = gateway.get("/users/1")
if response.is_success:
    user_data = response.json()
    print(user_data)

# Or use execute for full control
request = HttpRequest(
    url="/users",
    method=HttpMethod.POST,
    body={"name": "John", "email": "john@example.com"},
    headers={"Content-Type": "application/json"}
)
response = gateway.execute(request)

# Cleanup
gateway.close()

# Or use context manager
with ApiGateway(base_url="...", client=RequestsClient()) as gateway:
    response = gateway.get("/users")
```

---

## Benefits of New Architecture

### 1. Separation of Concerns
- Each class has a single, well-defined responsibility
- Easy to understand and maintain
- Changes to one component don't affect others

### 2. Testability
```python
# Easy to mock
class MockClient(HttpClient):
    def execute(self, request):
        return HttpResponse(
            status_code=200,
            headers={},
            body=b'{"success": true}',
            request=request
        )

gateway = ApiGateway(base_url="...", client=MockClient())
# Test without making real HTTP calls
```

### 3. Composability
```python
# Mix and match behaviors
gateway.add_middleware(RateLimitMiddleware(min_delay=0.5))
gateway.add_middleware(RetryMiddleware(max_retries=3))
gateway.add_middleware(LoggingMiddleware(io_manager))
gateway.add_middleware(CustomMiddleware())
```

### 4. Flexibility
- Swap HTTP client implementation without changing code
- Add new middleware without modifying existing code
- Support both sync and async operations

### 5. Type Safety
- No `Any` types (except for JSON body)
- Strong typing throughout
- Better IDE autocomplete and error detection

### 6. Thread Safety
- Immutable request/response objects
- No shared mutable state
- Safe for concurrent use

### 7. Future-Proof
- Easy to add async support
- Can switch HTTP libraries without breaking changes
- Extensible through middleware pattern

---

## Migration Strategy

### Phase 1: Parallel Implementation (No Breaking Changes)

1. Implement new architecture in parallel with existing code
2. Keep `AbstractGateway` as-is for backward compatibility
3. Create adapter/wrapper to use new architecture under the hood
4. Add deprecation warnings to old API

```python
# New code
from wexample_api.gateway import ApiGateway
from wexample_api.client.sync_client import RequestsClient

# Old code still works
from wexample_api.common.abstract_gateway import AbstractGateway
```

### Phase 2: Migration Period

1. Update documentation to recommend new API
2. Provide migration guide with examples
3. Migrate internal usage to new architecture
4. Keep old API functional but deprecated

**Migration Guide Example**:

```python
# OLD WAY
class MyGateway(AbstractGateway):
    def get_user(self, user_id: int):
        response = self.make_request(
            endpoint=f"/users/{user_id}",
            method=HttpMethod.GET,
            expected_status_codes=200,
        )
        return response.json() if response else None

gateway = MyGateway(base_url="https://api.example.com", io=io_manager)
user = gateway.get_user(1)

# NEW WAY
gateway = ApiGateway(
    base_url="https://api.example.com",
    client=RequestsClient(),
)
gateway.add_middleware(LoggingMiddleware(io_manager))

response = gateway.get("/users/1")
user = response.json() if response.is_success else None
```

### Phase 3: Deprecation

1. Set timeline for removal (e.g., 6 months)
2. Add clear deprecation warnings
3. Monitor usage through telemetry (if available)
4. Provide support for migration issues

### Phase 4: Removal

1. Remove old `AbstractGateway` implementation
2. Bump major version (breaking change)
3. Update all documentation
4. Celebrate cleaner codebase! 🎉

---

## Immediate Improvements (Without Full Rework)

If full rework is not immediately feasible, these changes can improve the current implementation:

### 1. Fix Default Status Code Behavior

```python
# Change from:
expected_status_codes: int | list[int] | None = None

# To:
expected_status_codes: int | list[int] | None = 200
```

This prevents accepting error responses by default.

### 2. Correct Type Annotations

```python
# Change from:
last_exception: Any = public_field(...)

# To:
last_exception: Exception | None = public_field(...)
```

### 3. Rename to English

```python
# Change:
check_connexion() -> check_connection()
```

### 4. Add Basic Retry Logic

```python
def make_request(
    self,
    endpoint: str,
    max_retries: int = 0,
    retry_on_status: set[int] = {429, 500, 502, 503, 504},
    **kwargs
) -> requests.Response | None:
    """Make HTTP request with optional retry logic."""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = self._execute_request(endpoint, **kwargs)
            
            # Don't retry if status code is not in retry set
            if response.status_code not in retry_on_status:
                return response
            
            # Last attempt, return even if failed
            if attempt == max_retries:
                return response
            
            # Exponential backoff
            time.sleep(2 ** attempt)
            
        except requests.exceptions.RequestException as exc:
            last_exception = exc
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)
    
    return None
```

### 5. Improve Documentation

Add comprehensive docstrings explaining:
- Parameter behaviors (especially `expected_status_codes=None`)
- Return value semantics
- Exception handling
- Thread safety considerations

```python
def make_request(
    self,
    endpoint: str,
    method: HttpMethod = HttpMethod.GET,
    expected_status_codes: int | list[int] | None = 200,
    ...
) -> requests.Response | None:
    """
    Make HTTP request to the API.
    
    Args:
        endpoint: API endpoint path (will be appended to base_url)
        method: HTTP method to use
        expected_status_codes: Expected HTTP status codes. If the response
            status code is not in this list, an error will be logged and
            None will be returned (unless fatal_if_unexpected=True).
            Default: 200 (only accept successful responses).
            WARNING: Setting to None accepts ALL status codes, including errors.
        data: Request body (dict for JSON, bytes for raw data)
        query_params: URL query parameters
        headers: Additional headers (merged with default_headers)
        fatal_if_unexpected: If True, raise exception on unexpected status
        quiet: If True, suppress logging output
        raise_exceptions: If True, raise exceptions instead of returning None
        
    Returns:
        Response object if successful, None if error occurred and not fatal.
        
    Raises:
        GatewayError: If fatal_if_unexpected=True or raise_exceptions=True
            and request fails.
        
    Example:
        response = gateway.make_request(
            endpoint="/users/1",
            method=HttpMethod.GET,
            expected_status_codes=200,
        )
        if response:
            user_data = response.json()
    """
```

---

## Testing Strategy

### Unit Tests

Each component should have comprehensive unit tests:

```python
# Test middleware in isolation
def test_rate_limit_middleware():
    middleware = RateLimitMiddleware(min_delay=1.0)
    request = HttpRequest(url="http://example.com", method=HttpMethod.GET)
    
    start = time.time()
    middleware.process_request(request)
    middleware.process_request(request)
    elapsed = time.time() - start
    
    assert elapsed >= 1.0

# Test client with mocked requests
@patch('requests.request')
def test_requests_client(mock_request):
    mock_request.return_value.status_code = 200
    mock_request.return_value.content = b'{"success": true}'
    
    client = RequestsClient()
    request = HttpRequest(url="http://example.com", method=HttpMethod.GET)
    response = client.execute(request)
    
    assert response.status_code == 200
    assert response.json() == {"success": true}

# Test gateway composition
def test_gateway_middleware_pipeline():
    client = MockClient()
    gateway = ApiGateway(base_url="http://example.com", client=client)
    
    middleware_calls = []
    
    class TrackingMiddleware(Middleware):
        def __init__(self, name):
            self.name = name
        
        def process_request(self, request):
            middleware_calls.append(f"{self.name}_request")
            return request
        
        def process_response(self, request, response):
            middleware_calls.append(f"{self.name}_response")
            return response
    
    gateway.add_middleware(TrackingMiddleware("A"))
    gateway.add_middleware(TrackingMiddleware("B"))
    
    gateway.get("/test")
    
    assert middleware_calls == [
        "A_request", "B_request",
        "B_response", "A_response"
    ]
```

### Integration Tests

Test real HTTP calls with test servers:

```python
def test_real_api_call():
    """Integration test with JSONPlaceholder API."""
    gateway = ApiGateway(
        base_url="https://jsonplaceholder.typicode.com",
        client=RequestsClient(),
    )
    
    response = gateway.get("/posts/1")
    
    assert response.is_success
    data = response.json()
    assert "title" in data
    assert "body" in data
```

---

## Performance Considerations

### Current Implementation
- Rate limiting adds delay to every request
- No connection pooling (creates new connection each time)
- Synchronous only (blocks on I/O)

### New Implementation
- Middleware can be selectively enabled
- Connection pooling through underlying client
- Async support for concurrent requests
- Better resource management

### Benchmarks to Track
- Requests per second
- Memory usage
- CPU usage
- Latency (p50, p95, p99)

---

## Documentation Requirements

### API Reference
- Complete docstrings for all public APIs
- Type hints for all parameters and return values
- Usage examples for each component

### User Guide
- Getting started tutorial
- Common patterns and recipes
- Migration guide from old API
- Best practices

### Developer Guide
- Architecture overview
- How to create custom middleware
- How to implement custom HTTP client
- Testing guidelines

---

## Success Criteria

The rework will be considered successful when:

1. **Code Quality**
   - All components have single responsibility
   - No circular dependencies
   - Type coverage > 95%
   - Test coverage > 90%

2. **Performance**
   - No performance regression vs current implementation
   - Async implementation 3x faster for concurrent requests

3. **Usability**
   - Migration guide covers all common use cases
   - Less than 20 lines of code for basic usage
   - Clear error messages

4. **Adoption**
   - All internal projects migrated
   - No critical bugs reported
   - Positive feedback from users

---

## Timeline Estimate

- **Phase 1** (Parallel Implementation): 2-3 weeks
- **Phase 2** (Migration Period): 4-6 weeks
- **Phase 3** (Deprecation): 3-6 months
- **Phase 4** (Removal): 1 week

**Total**: ~4-5 months from start to complete migration

---

## Open Questions

1. Should we support both sync and async in the same gateway, or separate classes?
2. What's the minimum Python version we want to support?
3. Do we need backward compatibility with the old API, or can we do a clean break?
4. Should middleware be able to short-circuit the request (e.g., return cached response)?
5. How should we handle streaming responses?
6. Do we need built-in support for pagination?

---

## References

- [Requests Documentation](https://requests.readthedocs.io/)
- [HTTPX Documentation](https://www.python-httpx.org/)
- [Middleware Pattern](https://en.wikipedia.org/wiki/Middleware)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
- [Immutability in Python](https://docs.python.org/3/library/dataclasses.html)
