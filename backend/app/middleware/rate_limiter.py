"""Simple in-memory rate limiter middleware.

Limits requests per IP using a sliding window.
Configure via settings: RATE_LIMIT_PER_MINUTE (default: 120).
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.window = 60  # seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, ip: str, now: float):
        cutoff = now - self.window
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for health checks and test clients
        if request.url.path in ("/health", "/health/ready"):
            return await call_next(request)
        if request.base_url.hostname == "test":
            return await call_next(request)

        ip = self._get_client_ip(request)
        now = time.time()
        self._cleanup(ip, now)

        if len(self._hits[ip]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"code": 42900, "message": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": "60"},
            )

        self._hits[ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.rpm - len(self._hits[ip])))
        return response
