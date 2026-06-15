"""Public Open API surface — `/openapi/v1/*`.

Isolated from the internal `/api/v1` routes: separate auth (app key / HMAC),
separate scopes, and an outward DTO layer. Business logic is not duplicated here —
queries go through the openapi service, which reads the same tables the internal
services own.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.domains.openapi import service, dto
from app.domains.openapi.auth import get_openapi_context, require_scope, OpenApiContext
from app.domains.openapi.errors import OpenApiException, CRM_NOT_FOUND

router = APIRouter(prefix="/openapi/v1", tags=["开放平台"])


# ---------------------------------------------------------------- responses
def _ok(request: Request, data):
    return {
        "code": 0,
        "message": "success",
        "traceId": getattr(request.state, "trace_id", None),
        "data": data,
    }


def _page(request: Request, items: list, total: int, page: int, page_size: int):
    return _ok(request, {"items": items, "total": total, "page": page, "page_size": page_size})


# -------------------------------------------------------------------- ping
@router.get("/ping")
async def ping(request: Request, ctx: OpenApiContext = Depends(get_openapi_context)):
    """Connectivity / credential self-check."""
    return _ok(request, {"app_key": ctx.app_key, "scopes": ctx.scopes, "tenant_id": ctx.tenant_id})


# --------------------------------------------------------------- customers
@router.get("/customers")
async def list_customers(
    request: Request,
    keyword: str | None = Query(None, description="按名称 / 客户编码模糊搜索"),
    status: str | None = Query(None),
    customer_code: str | None = Query(None),
    updated_since: str | None = Query(None, description="ISO 时间，仅返回该时间后更新的记录"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.customer.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_customers(
        db, ctx.tenant_id, keyword=keyword, status=status,
        customer_code=customer_code, updated_since=updated_since,
        page=page, page_size=page_size,
    )
    return _page(request, [dto.customer_to_dto(r) for r in rows], total, page, page_size)


@router.get("/customers/{customer_id}")
async def get_customer(
    request: Request, customer_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.customer.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_customer(db, ctx.tenant_id, customer_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "客户不存在", http_status=404, details={"id": customer_id})
    return _ok(request, dto.customer_to_dto(row))


@router.get("/customers/{customer_id}/contacts")
async def list_customer_contacts(
    request: Request, customer_id: str,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.contact.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_contacts(
        db, ctx.tenant_id, customer_id=customer_id, page=page, page_size=page_size,
    )
    return _page(request, [dto.contact_to_dto(r) for r in rows], total, page, page_size)


# ---------------------------------------------------------------- contacts
@router.get("/contacts")
async def list_contacts(
    request: Request,
    customer_id: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.contact.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_contacts(
        db, ctx.tenant_id, customer_id=customer_id, page=page, page_size=page_size,
    )
    return _page(request, [dto.contact_to_dto(r) for r in rows], total, page, page_size)


# ---------------------------------------------------------------- projects
@router.get("/projects")
async def list_projects(
    request: Request,
    customer_id: str | None = Query(None),
    stage_code: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.project.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_projects(
        db, ctx.tenant_id, customer_id=customer_id, stage_code=stage_code,
        status=status, page=page, page_size=page_size,
    )
    return _page(request, [dto.project_to_dto(r) for r in rows], total, page, page_size)


@router.get("/projects/{project_id}")
async def get_project(
    request: Request, project_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.project.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_project(db, ctx.tenant_id, project_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "商机项目不存在", http_status=404, details={"id": project_id})
    return _ok(request, dto.project_to_dto(row))


# --------------------------------------------------------------- contracts
@router.get("/contracts")
async def list_contracts(
    request: Request,
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.contract.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_contracts(
        db, ctx.tenant_id, project_id=project_id, status=status,
        page=page, page_size=page_size,
    )
    return _page(request, [dto.contract_to_dto(r) for r in rows], total, page, page_size)


@router.get("/contracts/{contract_id}")
async def get_contract(
    request: Request, contract_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.contract.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_contract(db, ctx.tenant_id, contract_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "合同不存在", http_status=404, details={"id": contract_id})
    return _ok(request, dto.contract_to_dto(row))


# ------------------------------------------------------------------ events
@router.get("/events")
async def list_events(
    request: Request,
    event_type: str | None = Query(None),
    after_event_id: str | None = Query(None, description="游标：返回该事件之后（更新）的事件"),
    occurred_from: str | None = Query(None, description="ISO 时间下界"),
    occurred_to: str | None = Query(None, description="ISO 时间上界"),
    limit: int = Query(50, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.event.read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.query_events(
        db, ctx.tenant_id, event_type=event_type, after_event_id=after_event_id,
        occurred_from=occurred_from, occurred_to=occurred_to, limit=limit,
    )
    items = [dto.event_to_dto(r) for r in rows]
    next_cursor = items[-1]["event_id"] if items else after_event_id
    return _ok(request, {"items": items, "limit": limit, "next_cursor": next_cursor})


@router.get("/events/{event_id}")
async def get_event(
    request: Request, event_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.event.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_event(db, ctx.tenant_id, event_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "事件不存在", http_status=404, details={"event_id": event_id})
    return _ok(request, dto.event_to_dto(row))
