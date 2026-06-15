"""Records one `openapi_call_logs` row per `/openapi/v1` request (metadata only).

Runs after the route (and its auth dependency) so it can read the resolved
``app_key`` / ``tenant_id`` and the final status code off ``request.state``.
Unauthenticated calls (no app resolved → no tenant to attribute the row to) are
skipped. Logging failures never affect the response.
"""
from __future__ import annotations

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.database import async_session_factory
from app.domains.openapi import service

logger = logging.getLogger("spt_crm.openapi")

_PREFIX = "/openapi/v1"


class OpenApiCallLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith(_PREFIX):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        app_key = getattr(request.state, "openapi_app_key", None)
        tenant_id = getattr(request.state, "openapi_tenant_id", None)
        if app_key and tenant_id:
            try:
                async with async_session_factory() as db:
                    await service.write_call_log(
                        db,
                        tenant_id=tenant_id,
                        app_key=app_key,
                        trace_id=getattr(request.state, "trace_id", None),
                        method=request.method,
                        path=request.url.path,
                        query_string=request.url.query or None,
                        status_code=response.status_code,
                        error_code=getattr(request.state, "openapi_error_code", None),
                        duration_ms=duration_ms,
                        client_ip=(request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                                   or (request.client.host if request.client else None)),
                    )
            except Exception as e:  # logging must never break the API
                logger.warning("openapi call-log write failed: %s", e)

        return response
