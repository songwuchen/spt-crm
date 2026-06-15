"""Public Open API surface — `/openapi/v1/*`.

Isolated from the internal `/api/v1` routes: separate auth (app key / HMAC),
separate scopes, and an outward DTO layer. Business logic is not duplicated here —
queries go through the openapi service, which reads the same tables the internal
services own.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Query
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.domains.openapi import service, dto
from app.domains.openapi.auth import get_openapi_context, require_scope, OpenApiContext
from app.domains.openapi.errors import OpenApiException, CRM_NOT_FOUND
from app.domains.openapi.schemas import (
    OpenLeadCreate, OpenActivityCreate, OpenCustomerCreate, OpenServiceTicketCreate,
)
from app.domains.openapi.idempotency import run_idempotent

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


# ----------------------------------------------- machine-readable discovery
_spec_cache: dict = {}


@router.get("/openapi.json", include_in_schema=False)
async def openapi_spec():
    """OpenAPI 3 schema for the public surface only (no auth needed — discovery)."""
    if "spec" not in _spec_cache:
        public_routes = [
            r for r in router.routes
            if getattr(r, "path", "").startswith("/openapi/v1")
            and not getattr(r, "path", "").endswith(("/openapi.json", "/docs"))
        ]
        schema = get_openapi(
            title="SPT-CRM 开放平台 API",
            version="v1",
            description="对外开放接口。认证：请求头 X-API-Key（API Key 模式）或 X-App-Id/X-Timestamp/X-Signature（HMAC 模式）。写接口需 Idempotency-Key。",
            routes=public_routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
            "type": "apiKey", "in": "header", "name": "X-API-Key",
        }
        schema["security"] = [{"ApiKeyAuth": []}]
        _spec_cache["spec"] = schema
    return JSONResponse(_spec_cache["spec"])


@router.get("/docs", include_in_schema=False)
async def openapi_docs():
    """Swagger UI for partners."""
    return get_swagger_ui_html(openapi_url="/openapi/v1/openapi.json", title="SPT-CRM 开放平台 API 文档")


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
    updated_since: str | None = Query(None, description="ISO 时间，增量同步"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.project.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_projects(
        db, ctx.tenant_id, customer_id=customer_id, stage_code=stage_code,
        status=status, updated_since=updated_since, page=page, page_size=page_size,
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


@router.get("/projects/{project_id}/stage-history")
async def list_stage_history(
    request: Request, project_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.project.read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.list_stage_history(db, ctx.tenant_id, project_id)
    if rows is None:
        raise OpenApiException(CRM_NOT_FOUND, "商机项目不存在", http_status=404, details={"id": project_id})
    return _ok(request, {"items": [dto.stage_history_to_dto(h) for h in rows]})


# --------------------------------------------------------------- contracts
@router.get("/contracts")
async def list_contracts(
    request: Request,
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    updated_since: str | None = Query(None, description="ISO 时间，增量同步"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.contract.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_contracts(
        db, ctx.tenant_id, project_id=project_id, status=status,
        updated_since=updated_since, page=page, page_size=page_size,
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


@router.get("/contracts/{contract_id}/versions")
async def list_contract_versions(
    request: Request, contract_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.contract.read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.list_contract_versions(db, ctx.tenant_id, contract_id)
    if rows is None:
        raise OpenApiException(CRM_NOT_FOUND, "合同不存在", http_status=404, details={"id": contract_id})
    return _ok(request, {"items": [dto.contract_version_to_dto(v) for v in rows]})


# ---------------------------------------------------------------- products
@router.get("/products")
async def list_products(
    request: Request,
    keyword: str | None = Query(None), is_active: bool | None = Query(None),
    updated_since: str | None = Query(None, description="ISO 时间，增量同步"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.product.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_products(db, ctx.tenant_id, keyword=keyword, is_active=is_active, updated_since=updated_since, page=page, page_size=page_size)
    return _page(request, [dto.product_to_dto(r) for r in rows], total, page, page_size)


@router.get("/products/{product_id}")
async def get_product(
    request: Request, product_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.product.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_product(db, ctx.tenant_id, product_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "产品不存在", http_status=404, details={"id": product_id})
    return _ok(request, dto.product_to_dto(row))


# ------------------------------------------------------------------ orders
@router.get("/orders")
async def list_orders(
    request: Request,
    customer_id: str | None = Query(None), status: str | None = Query(None),
    updated_since: str | None = Query(None, description="ISO 时间，增量同步"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.order.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_orders(db, ctx.tenant_id, customer_id=customer_id, status=status, updated_since=updated_since, page=page, page_size=page_size)
    return _page(request, [dto.order_to_dto(r) for r in rows], total, page, page_size)


@router.get("/orders/{order_id}")
async def get_order(
    request: Request, order_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.order.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_order(db, ctx.tenant_id, order_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "订单不存在", http_status=404, details={"id": order_id})
    return _ok(request, dto.order_to_dto(row))


# ------------------------------------------------------------------ quotes
@router.get("/quotes")
async def list_quotes(
    request: Request,
    project_id: str | None = Query(None), status: str | None = Query(None),
    updated_since: str | None = Query(None, description="ISO 时间，增量同步"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.quote.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_quotes(db, ctx.tenant_id, project_id=project_id, status=status, updated_since=updated_since, page=page, page_size=page_size)
    return _page(request, [dto.quote_to_dto(r) for r in rows], total, page, page_size)


@router.get("/quotes/{quote_id}")
async def get_quote(
    request: Request, quote_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.quote.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_quote(db, ctx.tenant_id, quote_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "报价不存在", http_status=404, details={"id": quote_id})
    return _ok(request, dto.quote_to_dto(row))


@router.get("/quotes/{quote_id}/lines")
async def get_quote_lines(
    request: Request, quote_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.quote.read")),
    db: AsyncSession = Depends(get_db),
):
    """Line items of the quote's current version (for ERP order creation)."""
    quote, version, lines = await service.get_quote_lines(db, ctx.tenant_id, quote_id)
    if not quote:
        raise OpenApiException(CRM_NOT_FOUND, "报价不存在", http_status=404, details={"id": quote_id})
    return _ok(request, {
        "quote_id": quote.id,
        "quote_no": quote.quote_no,
        "version_no": version.version_no if version else None,
        "price_total": float(version.price_total) if version and version.price_total else None,
        "items": [dto.quote_line_to_dto(li) for li in lines],
    })


@router.get("/quotes/{quote_id}/versions")
async def list_quote_versions(
    request: Request, quote_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.quote.read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.list_quote_versions(db, ctx.tenant_id, quote_id)
    if rows is None:
        raise OpenApiException(CRM_NOT_FOUND, "报价不存在", http_status=404, details={"id": quote_id})
    return _ok(request, {"items": [dto.quote_version_to_dto(v) for v in rows]})


# ---------------------------------------------------------------- payments
@router.get("/payments")
async def list_payments(
    request: Request,
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.payment.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_payments(db, ctx.tenant_id, project_id=project_id, page=page, page_size=page_size)
    return _page(request, [dto.payment_to_dto(r) for r in rows], total, page, page_size)


# ----------------------------------------------------------- service tickets
@router.get("/service-tickets")
async def list_service_tickets(
    request: Request,
    customer_id: str | None = Query(None), status: str | None = Query(None),
    updated_since: str | None = Query(None, description="ISO 时间，增量同步"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.service.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_service_tickets(db, ctx.tenant_id, customer_id=customer_id, status=status, updated_since=updated_since, page=page, page_size=page_size)
    return _page(request, [dto.service_ticket_to_dto(r) for r in rows], total, page, page_size)


@router.get("/service-tickets/{ticket_id}")
async def get_service_ticket(
    request: Request, ticket_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.service.read")),
    db: AsyncSession = Depends(get_db),
):
    row = await service.get_service_ticket(db, ctx.tenant_id, ticket_id)
    if not row:
        raise OpenApiException(CRM_NOT_FOUND, "工单不存在", http_status=404, details={"id": ticket_id})
    return _ok(request, dto.service_ticket_to_dto(row))


# ------------------------------------------------------- delivery milestones
@router.get("/milestones")
async def list_milestones(
    request: Request,
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    ctx: OpenApiContext = Depends(require_scope("crm.delivery.read")),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await service.query_milestones(db, ctx.tenant_id, project_id=project_id, page=page, page_size=page_size)
    return _page(request, [dto.milestone_to_dto(r) for r in rows], total, page, page_size)


# --------------------------------------------------------- leads (write)
@router.post("/leads")
async def create_lead(
    request: Request, body: OpenLeadCreate,
    ctx: OpenApiContext = Depends(require_scope("crm.lead.write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a lead. **Requires** an ``Idempotency-Key`` header; replays with the
    same key + body return the original result without creating a duplicate."""
    async def producer():
        return await service.create_lead_from_openapi(db, ctx, body)

    data = await run_idempotent(db, ctx, request, producer)
    return _ok(request, data)


@router.post("/leads/{lead_id}/qualify")
async def qualify_lead(
    request: Request, lead_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.lead.write")),
    db: AsyncSession = Depends(get_db),
):
    """Convert a lead into a customer. Requires ``Idempotency-Key``."""
    async def producer():
        return await service.qualify_lead_from_openapi(db, ctx, lead_id)
    return _ok(request, await run_idempotent(db, ctx, request, producer))


@router.post("/leads/{lead_id}/discard")
async def discard_lead(
    request: Request, lead_id: str,
    ctx: OpenApiContext = Depends(require_scope("crm.lead.write")),
    db: AsyncSession = Depends(get_db),
):
    """Discard a lead. Requires ``Idempotency-Key``."""
    async def producer():
        return await service.discard_lead_from_openapi(db, ctx, lead_id)
    return _ok(request, await run_idempotent(db, ctx, request, producer))


# ------------------------------------------------------------- activities (write)
@router.post("/activities")
async def create_activity(
    request: Request, body: OpenActivityCreate,
    ctx: OpenApiContext = Depends(require_scope("crm.activity.write")),
    db: AsyncSession = Depends(get_db),
):
    """Log a follow-up / activity. Requires ``Idempotency-Key``."""
    async def producer():
        return await service.create_activity_from_openapi(db, ctx, body)
    return _ok(request, await run_idempotent(db, ctx, request, producer))


# -------------------------------------------------------------- customers (write)
@router.post("/customers")
async def create_customer(
    request: Request, body: OpenCustomerCreate,
    ctx: OpenApiContext = Depends(require_scope("crm.customer.write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a customer (unassigned/public pool). Requires ``Idempotency-Key``."""
    async def producer():
        return await service.create_customer_from_openapi(db, ctx, body)
    return _ok(request, await run_idempotent(db, ctx, request, producer))


# --------------------------------------------------------- service tickets (write)
@router.post("/service-tickets")
async def create_service_ticket(
    request: Request, body: OpenServiceTicketCreate,
    ctx: OpenApiContext = Depends(require_scope("crm.service.write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a support ticket (SLA timers applied). Requires ``Idempotency-Key``."""
    async def producer():
        return await service.create_service_ticket_from_openapi(db, ctx, body)
    return _ok(request, await run_idempotent(db, ctx, request, producer))


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
