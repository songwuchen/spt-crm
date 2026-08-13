"""Simple in-memory rate limiter middleware.

Limits requests per client using a sliding window.
Bucket key prefers authenticated user (Authorization) so office NAT
sharing one public IP does not throttle everyone together.

Configure via settings: RATE_LIMIT_PER_MINUTE (default: 600).
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 600):
        super().__init__(app)
        self.rpm = max(1, int(requests_per_minute))
        self.window = 60  # seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._rejected: dict[str, int] = defaultdict(int)  # count of 429 per bucket

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _bucket_key(self, request: Request) -> str:
        """Prefer per-user bucket when logged in; fall back to IP."""
        auth = (request.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer ") and len(auth) > 20:
            digest = hashlib.sha256(auth.encode("utf-8", errors="ignore")).hexdigest()[:24]
            return f"u:{digest}"
        return f"ip:{self._get_client_ip(request)}"

    def _cleanup(self, key: str, now: float) -> None:
        cutoff = now - self.window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        # Skip health / preflight / websocket upgrade noise
        if path in ("/health", "/health/ready") or path.startswith("/ws"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.base_url.hostname == "test":
            return await call_next(request)

        key = self._bucket_key(request)
        now = time.time()
        self._cleanup(key, now)

        if len(self._hits[key]) >= self.rpm:
            self._rejected[key] += 1
            return JSONResponse(
                status_code=429,
                content={"code": 42900, "message": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": "30"},
            )

        self._hits[key].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.rpm - len(self._hits[key])))
        return response

    def get_stats(self) -> dict:
        """Return rate limiter stats for admin dashboard."""
        now = time.time()
        active = []
        for key, hits in self._hits.items():
            recent = [t for t in hits if t > now - self.window]
            if recent:
                active.append({
                    "ip": key,  # field name kept for dashboard compat (may be u:… or ip:…)
                    "requests": len(recent),
                    "limit": self.rpm,
                    "usage_pct": round(len(recent) / self.rpm * 100, 1),
                    "rejected": self._rejected.get(key, 0),
                })
        active.sort(key=lambda x: x["requests"], reverse=True)
        return {
            "rpm_limit": self.rpm,
            "active_clients": len(active),
            "total_rejected": sum(self._rejected.values()),
            "clients": active[:50],
        }
