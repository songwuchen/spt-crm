from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.common.exceptions import BusinessException
from app.common.error_codes import VALIDATION_ERROR, UNAUTHORIZED


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=200,
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
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=500,
        content={"code": 50000, "message": "服务器内部错误", "data": None, "traceId": trace_id},
    )
