import uuid
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.common.context import request_ip, request_trace_id, request_user_agent

logger = logging.getLogger("spt_crm.request")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        # Populate context vars for audit logging
        request_trace_id.set(trace_id)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        )
        request_ip.set(client_ip)
        request_user_agent.set(request.headers.get("User-Agent"))

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Trace-Id"] = trace_id

        # Log request (skip health check and static)
        path = request.url.path
        if path not in ("/health", "/favicon.ico"):
            logger.info(
                "%s %s %s %sms [%s] %s",
                request.method, path, response.status_code,
                elapsed_ms, client_ip or "-", trace_id[:8],
            )

        return response
