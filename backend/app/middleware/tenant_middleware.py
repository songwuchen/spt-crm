from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant_id from the authenticated user and store in request.state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # tenant_id is set by the auth dependency after JWT decode.
        # This middleware just ensures the attribute exists for downstream code.
        if not hasattr(request.state, "tenant_id"):
            request.state.tenant_id = None
        response = await call_next(request)
        return response
