from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.common.exceptions import BusinessException
from app.common.error_codes import VALIDATION_ERROR, UNAUTHORIZED


_CODE_TO_HTTP: dict[int, int] = {
    40100: 401, 40101: 401, 40102: 401,  # Auth errors
    40300: 403,                            # Forbidden
    40400: 404,                            # Not found
    42200: 422, 42201: 409,               # Validation / Duplicate
}


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    http_status = _CODE_TO_HTTP.get(exc.code, 400)
    return JSONResponse(
        status_code=http_status,
        content={"code": exc.code, "message": exc.message, "data": exc.detail, "traceId": trace_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    details = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"])
        details.append(f"{field}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content={
            "code": VALIDATION_ERROR,
            "message": "; ".join(details),
            "data": None,
            "traceId": trace_id,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logging.getLogger("spt_crm.error").exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=500,
        content={"code": 50000, "message": "服务器内部错误", "data": None, "traceId": trace_id},
    )
