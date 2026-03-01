from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.service_ticket import service
from app.domains.service_ticket.schemas import (
    ServiceTicketCreate, ServiceTicketUpdate, RenewalCreate, RenewalUpdate,
)

router = APIRouter(tags=["售后管理"])


def _ticket_dict(t) -> dict:
    return {
        "id": t.id, "customer_id": t.customer_id, "project_id": t.project_id,
        "ticket_no": t.ticket_no, "type": t.type,
        "priority": t.priority, "status": t.status,
        "description": t.description, "resolution": t.resolution,
        "ai_summary_json": t.ai_summary_json,
        "assigned_to_id": t.assigned_to_id, "assigned_to_name": t.assigned_to_name,
        "created_by_id": t.created_by_id, "created_by_name": t.created_by_name,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


def _renewal_dict(r) -> dict:
    return {
        "id": r.id, "customer_id": r.customer_id,
        "name": r.name,
        "amount_expect": float(r.amount_expect) if r.amount_expect is not None else None,
        "close_date_expect": str(r.close_date_expect) if r.close_date_expect else None,
        "probability": r.probability,
        "related_asset_json": r.related_asset_json,
        "status": r.status,
        "owner_id": r.owner_id, "owner_name": r.owner_name,
        "remark": r.remark,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


# --- Export ---

@router.get("/api/v1/service_tickets/export/excel")
async def export_tickets_excel(
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    items, _ = await service.list_tickets(db, tenant_id, page_size=10000)
    headers = ["工单编号", "类型", "优先级", "状态", "描述", "处理结果", "负责人", "创建人", "创建时间"]
    rows = []
    for t in items:
        rows.append([
            t.ticket_no, t.type or "", t.priority or "", t.status or "",
            t.description or "", t.resolution or "",
            t.assigned_to_name or "", t.created_by_name or "",
            t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
        ])
    buf = build_excel("售后工单", headers, rows)
    return excel_response(buf, "service_tickets.xlsx")


# --- ServiceTicket ---

@router.get("/api/v1/service_tickets")
async def list_tickets(
    customer_id: str | None = Query(None), project_id: str | None = Query(None),
    keyword: str | None = Query(None), status: str | None = Query(None),
    pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    items, total = await service.list_tickets(
        db, tenant_id, customer_id=customer_id, project_id=project_id,
        keyword=keyword, status=status, page=pageNo, page_size=pageSize,
    )
    return ok({"items": [_ticket_dict(t) for t in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/api/v1/service_tickets")
async def create_ticket(
    body: ServiceTicketCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("service:create")),
):
    t = await service.create_ticket(db, tenant_id, body, current_user)
    return ok(_ticket_dict(t))


@router.get("/api/v1/service_tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("service:view")),
):
    t = await service.get_ticket(db, tenant_id, ticket_id)
    return ok(_ticket_dict(t))


@router.put("/api/v1/service_tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str, body: ServiceTicketUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("service:edit")),
):
    t = await service.update_ticket(db, tenant_id, ticket_id, body, current_user)
    return ok(_ticket_dict(t))


@router.delete("/api/v1/service_tickets/{ticket_id}")
async def delete_ticket(
    ticket_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("service:delete")),
):
    await service.delete_ticket(db, tenant_id, ticket_id, current_user)
    return ok(None)


# --- RenewalOpportunity ---

@router.get("/api/v1/renewal_opportunities")
async def list_renewals(
    customer_id: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    items = await service.list_renewals(db, tenant_id, customer_id=customer_id)
    return ok([_renewal_dict(r) for r in items])


@router.post("/api/v1/renewal_opportunities")
async def create_renewal(
    body: RenewalCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("service:create")),
):
    r = await service.create_renewal(db, tenant_id, body, current_user)
    return ok(_renewal_dict(r))


@router.get("/api/v1/renewal_opportunities/{renewal_id}")
async def get_renewal(
    renewal_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("service:view")),
):
    r = await service.get_renewal(db, tenant_id, renewal_id)
    return ok(_renewal_dict(r))


@router.put("/api/v1/renewal_opportunities/{renewal_id}")
async def update_renewal(
    renewal_id: str, body: RenewalUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("service:edit")),
):
    r = await service.update_renewal(db, tenant_id, renewal_id, body, current_user)
    return ok(_renewal_dict(r))
