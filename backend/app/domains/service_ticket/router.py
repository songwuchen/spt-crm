from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.service_ticket import service
from app.domains.service_ticket.schemas import (
    ServiceTicketCreate, ServiceTicketUpdate, RenewalCreate, RenewalUpdate,
)
from app.domains.customer.models import Customer

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
        "sla_respond_by": t.sla_respond_by.isoformat() if t.sla_respond_by else None,
        "sla_resolve_by": t.sla_resolve_by.isoformat() if t.sla_resolve_by else None,
        "sla_responded_at": t.sla_responded_at.isoformat() if t.sla_responded_at else None,
        "sla_resolved_at": t.sla_resolved_at.isoformat() if t.sla_resolved_at else None,
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
    priority: str | None = Query(None), type: str | None = Query(None),
    pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    items, total = await service.list_tickets(
        db, tenant_id, customer_id=customer_id, project_id=project_id,
        keyword=keyword, status=status, priority=priority, ticket_type=type,
        page=pageNo, page_size=pageSize,
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
    status: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    items = await service.list_renewals(db, tenant_id, customer_id=customer_id, status=status)
    # Batch lookup customer names
    cust_ids = list({r.customer_id for r in items if r.customer_id})
    cust_names: dict[str, str] = {}
    if cust_ids:
        rows = (await db.execute(
            select(Customer.id, Customer.name).where(Customer.id.in_(cust_ids))
        )).all()
        cust_names = {r.id: r.name for r in rows}
    result = []
    for r in items:
        d = _renewal_dict(r)
        d["customer_name"] = cust_names.get(r.customer_id, "")
        result.append(d)
    return ok(result)


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


# --- SLA Management ---

# Default SLA hours by priority
DEFAULT_SLA_HOURS = {
    "critical": 4,
    "high": 8,
    "medium": 24,
    "low": 72,
}


@router.get("/api/v1/service_tickets/sla/stats")
async def sla_stats(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    """SLA statistics: on-time rate, average resolution time, breach count."""
    from sqlalchemy import func, case
    from datetime import datetime, timezone, timedelta
    from app.domains.service_ticket.models import ServiceTicket

    # Open/active tickets with SLA status
    open_tickets = (await db.execute(
        select(func.count(ServiceTicket.id)).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    )).scalar() or 0

    resolved_tickets = (await db.execute(
        select(func.count(ServiceTicket.id)).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.in_(["resolved", "closed"]),
        )
    )).scalar() or 0

    # Calculate SLA breaches for open tickets
    now = datetime.now(timezone.utc)
    breach_count = 0
    near_breach_count = 0

    open_items = (await db.execute(
        select(ServiceTicket).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    )).scalars().all()

    for t in open_items:
        sla_hours = DEFAULT_SLA_HOURS.get(t.priority, 24)
        if t.created_at:
            created = t.created_at.replace(tzinfo=timezone.utc) if t.created_at.tzinfo is None else t.created_at
            deadline = created + timedelta(hours=sla_hours)
            if now > deadline:
                breach_count += 1
            elif now > deadline - timedelta(hours=max(1, sla_hours * 0.2)):
                near_breach_count += 1

    # By priority distribution
    priority_rows = (await db.execute(
        select(ServiceTicket.priority, func.count(ServiceTicket.id).label("count")).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.in_(["open", "assigned", "in_progress"]),
        ).group_by(ServiceTicket.priority)
    )).all()

    by_priority = {r.priority: r.count for r in priority_rows}

    total = open_tickets + resolved_tickets
    on_time_rate = round((total - breach_count) / total * 100, 1) if total > 0 else 100

    return ok({
        "open_tickets": open_tickets,
        "resolved_tickets": resolved_tickets,
        "breach_count": breach_count,
        "near_breach_count": near_breach_count,
        "on_time_rate": on_time_rate,
        "sla_config": DEFAULT_SLA_HOURS,
        "by_priority": by_priority,
    })


@router.get("/api/v1/service_tickets/knowledge")
async def knowledge_search(
    keyword: str = Query(..., min_length=2),
    ticket_type: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("service:view")),
):
    """Search resolved tickets as knowledge base for similar solutions."""
    from sqlalchemy import or_
    from app.domains.service_ticket.models import ServiceTicket

    q = select(ServiceTicket).where(
        ServiceTicket.tenant_id == tenant_id,
        ServiceTicket.status.in_(["resolved", "closed"]),
        ServiceTicket.resolution != None,
        or_(
            ServiceTicket.description.ilike(f"%{keyword}%"),
            ServiceTicket.resolution.ilike(f"%{keyword}%"),
            ServiceTicket.ticket_no.ilike(f"%{keyword}%"),
        ),
    )
    if ticket_type:
        q = q.where(ServiceTicket.type == ticket_type)
    q = q.order_by(ServiceTicket.updated_at.desc()).limit(20)

    items = (await db.execute(q)).scalars().all()
    return ok([{
        "id": t.id,
        "ticket_no": t.ticket_no,
        "type": t.type,
        "priority": t.priority,
        "description": (t.description or "")[:200],
        "resolution": (t.resolution or "")[:500],
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    } for t in items])
