from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openpyxl import load_workbook
import io

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions, get_data_scope
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.customer.models import Customer
from app.domains.customer.schemas import (
    CustomerCreate, CustomerUpdate, CustomerOut,
    ContactCreate, ContactUpdate, ContactOut,
)
from app.domains.customer import service

router = APIRouter(prefix="/api/v1/customers", tags=["客户管理"])


def _customer_dict(c) -> dict:
    return {
        "id": c.id, "customer_code": c.customer_code,
        "name": c.name, "short_name": c.short_name,
        "industry": c.industry, "scale_level": c.scale_level,
        "region": c.region, "address": c.address, "website": c.website,
        "owner_id": c.owner_id, "owner_name": c.owner_name,
        "source": c.source, "level": c.level, "status": c.status,
        "tags_json": c.tags_json, "remark": c.remark, "custom_fields_json": c.custom_fields_json,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


@router.get("")
async def list_customers(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    industry: str = Query(None),
    region: str = Query(None),
    owner_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
    data_scope: str | None = Depends(get_data_scope),
):
    effective_owner = owner_id or data_scope
    items, total = await service.list_customers(db, tenant_id, pageNo, pageSize, keyword, industry, region, effective_owner)
    return ok({"items": [_customer_dict(c) for c in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("")
async def create_customer(
    body: CustomerCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:create")),
):
    c = await service.create_customer(db, tenant_id, body, current_user)
    return ok(_customer_dict(c))


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    c = await service.get_customer(db, tenant_id, customer_id)
    return ok(_customer_dict(c))


@router.put("/{customer_id}")
async def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    c = await service.update_customer(db, tenant_id, customer_id, body, current_user)
    return ok(_customer_dict(c))


@router.get("/export/excel")
async def export_customers_excel(
    keyword: str = Query(None),
    industry: str = Query(None),
    region: str = Query(None),
    owner_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    items, _ = await service.list_customers(db, tenant_id, 1, 5000, keyword, industry, region, owner_id)
    headers = ["客户编码", "客户名称", "简称", "行业", "规模", "地区", "地址", "负责人", "来源", "级别", "状态", "创建时间"]
    rows = []
    for c in items:
        rows.append([
            c.customer_code, c.name, c.short_name or "", c.industry or "",
            c.scale_level or "", c.region or "", c.address or "",
            c.owner_name or "", c.source or "", c.level or "", c.status or "",
            c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
        ])
    buf = build_excel("客户列表", headers, rows)
    return excel_response(buf, "customers.xlsx")


# ---- Customer Pool (公海池) ----

@router.get("/pool")
async def list_pool_customers(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    industry: str = Query(None),
    region: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    items, total = await service.list_pool_customers(db, tenant_id, pageNo, pageSize, keyword, industry, region)
    return ok({"items": [_customer_dict(c) for c in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/{customer_id}/release")
async def release_to_pool(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    c = await service.release_to_pool(db, tenant_id, customer_id, current_user)
    return ok(_customer_dict(c))


@router.post("/{customer_id}/claim")
async def claim_from_pool(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    c = await service.claim_from_pool(db, tenant_id, customer_id, current_user)
    return ok(_customer_dict(c))


@router.post("/batch_release")
async def batch_release(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    ids = body.get("customer_ids", [])
    released = await service.batch_release_to_pool(db, tenant_id, ids, current_user)
    return ok({"released": released})


@router.post("/import/preview")
async def import_preview(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:create")),
):
    """Parse Excel and return headers + rows + duplicate detection."""
    from sqlalchemy import select as sa_select
    content = await file.read()
    wb = load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not all_rows:
        return ok({"headers": [], "rows": [], "duplicates": []})

    headers = [str(c).strip() if c else f"列{i+1}" for i, c in enumerate(all_rows[0])]
    data_rows = []
    names = []
    for row in all_rows[1:]:
        if not row or not any(row):
            continue
        cells = [str(c).strip() if c is not None else "" for c in row]
        # pad to header length
        while len(cells) < len(headers):
            cells.append("")
        data_rows.append(cells[:len(headers)])
        if cells:
            names.append(cells[0])

    # Detect duplicates by name
    from app.domains.customer.models import Customer
    existing = set()
    if names:
        result = await db.execute(
            sa_select(Customer.name).where(
                Customer.tenant_id == tenant_id,
                Customer.is_deleted == False,
                Customer.name.in_(names),
            )
        )
        existing = {r[0] for r in result.all()}

    duplicates = [i for i, name in enumerate(names) if name in existing]

    return ok({"headers": headers, "rows": data_rows, "duplicates": duplicates})


@router.post("/import/excel")
async def import_customers_excel(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:create")),
):
    """Import customers from Excel with field mapping and duplicate handling."""
    from starlette.datastructures import UploadFile as StarletteUpload
    import json as json_mod

    content = await file.read()
    wb = load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if len(all_rows) < 2:
        return ok({"created": 0, "skipped": 0, "errors": []})

    # Parse field_mapping and skip_duplicates from form multipart (sent as query or form fields)
    from starlette.requests import Request
    # Fallback: default column mapping
    default_fields = ["name", "short_name", "industry", "scale_level", "region", "address", "source", "level"]

    headers = all_rows[0]
    data_rows = all_rows[1:]

    # Detect duplicates
    from sqlalchemy import select as sa_select
    from app.domains.customer.models import Customer
    names = []
    for row in data_rows:
        if row and row[0]:
            names.append(str(row[0]).strip())
    existing_names = set()
    if names:
        result = await db.execute(
            sa_select(Customer.name).where(
                Customer.tenant_id == tenant_id,
                Customer.is_deleted == False,
                Customer.name.in_(names),
            )
        )
        existing_names = {r[0] for r in result.all()}

    created = 0
    skipped = 0
    errors = []
    for idx, row in enumerate(data_rows, 2):
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        if name in existing_names:
            skipped += 1
            continue
        try:
            data = CustomerCreate(
                name=name,
                short_name=str(row[1]).strip() if len(row) > 1 and row[1] else None,
                industry=str(row[2]).strip() if len(row) > 2 and row[2] else None,
                scale_level=str(row[3]).strip() if len(row) > 3 and row[3] else None,
                region=str(row[4]).strip() if len(row) > 4 and row[4] else None,
                address=str(row[5]).strip() if len(row) > 5 and row[5] else None,
                source=str(row[6]).strip() if len(row) > 6 and row[6] else None,
                level=str(row[7]).strip() if len(row) > 7 and row[7] else None,
            )
            await service.create_customer(db, tenant_id, data, current_user)
            created += 1
            existing_names.add(name)  # prevent duplicates within same batch
        except Exception as e:
            errors.append(f"第{idx}行: {str(e)[:80]}")
    return ok({"created": created, "skipped": skipped, "errors": errors})


@router.get("/{customer_id}/stats")
async def customer_stats(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    """Customer 360 stats: project/quote/contract/ticket counts + totals."""
    from sqlalchemy import select, func
    from app.domains.project.models import OpportunityProject
    from app.domains.quote.models import Quote
    from app.domains.contract.models import Contract
    from app.domains.service_ticket.models import ServiceTicket

    project_count = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.customer_id == customer_id)
    )).scalar() or 0

    project_amount = (await db.execute(
        select(func.sum(OpportunityProject.amount_expect)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.customer_id == customer_id,
            OpportunityProject.status == "active")
    )).scalar() or 0

    # Get project IDs for this customer
    proj_ids = (await db.execute(
        select(OpportunityProject.id).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.customer_id == customer_id)
    )).scalars().all()

    quote_count = 0
    contract_count = 0
    contract_amount = 0
    if proj_ids:
        quote_count = (await db.execute(
            select(func.count(Quote.id)).where(Quote.tenant_id == tenant_id, Quote.project_id.in_(proj_ids))
        )).scalar() or 0
        contract_count = (await db.execute(
            select(func.count(Contract.id)).where(Contract.tenant_id == tenant_id, Contract.project_id.in_(proj_ids))
        )).scalar() or 0
        contract_amount = (await db.execute(
            select(func.sum(Contract.amount_total)).where(
                Contract.tenant_id == tenant_id, Contract.project_id.in_(proj_ids), Contract.status == "signed")
        )).scalar() or 0

    ticket_count = (await db.execute(
        select(func.count(ServiceTicket.id)).where(
            ServiceTicket.tenant_id == tenant_id, ServiceTicket.customer_id == customer_id)
    )).scalar() or 0

    ticket_open = (await db.execute(
        select(func.count(ServiceTicket.id)).where(
            ServiceTicket.tenant_id == tenant_id, ServiceTicket.customer_id == customer_id,
            ServiceTicket.status.in_(["open", "in_progress"]))
    )).scalar() or 0

    # Won/lost counts
    won_count = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.customer_id == customer_id,
            OpportunityProject.status == "won")
    )).scalar() or 0
    lost_count = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.customer_id == customer_id,
            OpportunityProject.status == "lost")
    )).scalar() or 0

    # Payment collection rate
    collection_rate = 0.0
    if proj_ids:
        from app.domains.payment.models import PaymentPlan, PaymentRecord
        plan_total = float((await db.execute(
            select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
                PaymentPlan.tenant_id == tenant_id, PaymentPlan.project_id.in_(proj_ids))
        )).scalar() or 0)
        received_total = float((await db.execute(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id, PaymentRecord.project_id.in_(proj_ids))
        )).scalar() or 0)
        collection_rate = (received_total / plan_total) if plan_total > 0 else 0.0

    win_rate = (won_count / (won_count + lost_count)) if (won_count + lost_count) > 0 else 0.0

    return ok({
        "project_count": project_count,
        "project_amount": float(project_amount),
        "quote_count": quote_count,
        "contract_count": contract_count,
        "contract_amount": float(contract_amount or 0),
        "ticket_count": ticket_count,
        "ticket_open": ticket_open,
        "won_count": won_count,
        "lost_count": lost_count,
        "win_rate": round(win_rate, 3),
        "collection_rate": round(collection_rate, 3),
    })


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:delete")),
):
    await service.delete_customer(db, tenant_id, customer_id, current_user)
    return ok()


# ---- Contact sub-resource ----
@router.get("/{customer_id}/contacts")
async def list_contacts(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contact:view")),
):
    contacts = await service.list_contacts(db, tenant_id, customer_id)
    return ok([ContactOut.model_validate(c).model_dump() for c in contacts])


@router.post("/{customer_id}/contacts")
async def create_contact(
    customer_id: str,
    body: ContactCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contact:create")),
):
    c = await service.create_contact(db, tenant_id, customer_id, body, current_user)
    return ok(ContactOut.model_validate(c).model_dump())


@router.put("/{customer_id}/contacts/{contact_id}")
async def update_contact(
    customer_id: str,
    contact_id: str,
    body: ContactUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contact:edit")),
):
    c = await service.update_contact(db, tenant_id, contact_id, body, current_user)
    return ok(ContactOut.model_validate(c).model_dump())


@router.delete("/{customer_id}/contacts/{contact_id}")
async def delete_contact(
    customer_id: str,
    contact_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contact:delete")),
):
    await service.delete_contact(db, tenant_id, contact_id, current_user)
    return ok()


# ---- Customer Relations ----
@router.get("/{customer_id}/relations")
async def list_relations(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    items = await service.list_relations(db, tenant_id, customer_id)
    return ok([{
        "id": r.id, "from_customer_id": r.from_customer_id,
        "to_customer_id": r.to_customer_id, "relation_type": r.relation_type,
        "note": r.note, "created_at": r.created_at.isoformat() if r.created_at else "",
    } for r in items])


@router.post("/{customer_id}/relations")
async def create_relation(
    customer_id: str,
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    body["from_customer_id"] = customer_id
    r = await service.create_relation(db, tenant_id, body, current_user)
    return ok({"id": r.id, "relation_type": r.relation_type})


@router.delete("/{customer_id}/relations/{relation_id}")
async def delete_relation(
    customer_id: str,
    relation_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    await service.delete_relation(db, tenant_id, relation_id, current_user)
    return ok()


# ---- ACL Shares (generic) ----
@router.get("/{customer_id}/shares")
async def list_shares(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    items = await service.list_shares(db, tenant_id, "customer", customer_id)
    return ok([{
        "id": s.id, "biz_type": s.biz_type, "biz_id": s.biz_id,
        "shared_to_type": s.shared_to_type, "shared_to_id": s.shared_to_id,
        "shared_to_name": s.shared_to_name, "permission": s.permission,
        "shared_by_name": s.shared_by_name,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    } for s in items])


@router.post("/{customer_id}/shares")
async def create_share(
    customer_id: str,
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    body["biz_type"] = "customer"
    body["biz_id"] = customer_id
    s = await service.create_share(db, tenant_id, body, current_user)
    return ok({"id": s.id, "shared_to_name": s.shared_to_name})


@router.delete("/{customer_id}/shares/{share_id}")
async def delete_share(
    customer_id: str,
    share_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    await service.delete_share(db, tenant_id, share_id, current_user)
    return ok()


@router.get("/check-similar")
async def check_similar(
    name: str = Query(..., min_length=2),
    exclude_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Find customers with similar names for duplicate detection."""
    from sqlalchemy import or_
    q = select(Customer.id, Customer.name, Customer.short_name, Customer.industry, Customer.owner_name).where(
        Customer.tenant_id == tenant_id,
        Customer.is_deleted == False,
        or_(Customer.name.ilike(f"%{name}%"), Customer.short_name.ilike(f"%{name}%")),
    )
    if exclude_id:
        q = q.where(Customer.id != exclude_id)
    items = (await db.execute(q.limit(5))).all()
    return ok([{"id": r.id, "name": r.name, "short_name": r.short_name, "industry": r.industry, "owner_name": r.owner_name} for r in items])


@router.get("/check-unique")
async def check_unique(
    field: str = Query(..., pattern=r"^(name|customer_code)$"),
    value: str = Query(..., min_length=1),
    exclude_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Check if a customer field value is unique within the tenant."""
    col = Customer.name if field == "name" else Customer.customer_code
    q = select(Customer.id).where(
        Customer.tenant_id == tenant_id,
        Customer.is_deleted == False,
        col == value,
    )
    if exclude_id:
        q = q.where(Customer.id != exclude_id)
    exists = (await db.execute(q)).scalar() is not None
    return ok({"unique": not exists})


# ---- Batch Operations ----

from pydantic import BaseModel as PydanticBaseModel


class CustomerMergeBody(PydanticBaseModel):
    primary_id: str
    secondary_id: str


@router.post("/merge")
async def merge_customers(
    body: CustomerMergeBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    """Merge secondary customer into primary, moving all related data."""
    c = await service.merge_customers(db, tenant_id, body.primary_id, body.secondary_id, current_user)
    return ok(_customer_dict(c))


class BatchTransferBody(PydanticBaseModel):
    ids: list[str]
    owner_id: str
    owner_name: str | None = None


@router.post("/batch_transfer")
async def batch_transfer(
    body: BatchTransferBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    """Batch transfer customers to a new owner."""
    from sqlalchemy import update
    result = await db.execute(
        update(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id.in_(body.ids),
            Customer.is_deleted == False,
        ).values(owner_id=body.owner_id, owner_name=body.owner_name)
    )
    await db.commit()
    return ok({"updated": result.rowcount})


@router.get("/{customer_id}/health")
async def customer_health(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Compute a health score (0-100, grade A-D) for a customer."""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.domains.project.models import OpportunityProject
    from app.domains.payment.models import PaymentPlan, PaymentRecord
    from app.domains.service_ticket.models import ServiceTicket
    from app.domains.activity.models import Activity

    now = datetime.utcnow()
    d90 = now - timedelta(days=90)

    # 1. Recent activity count (max 30 pts)
    activity_count = (await db.execute(
        select(func.count()).where(
            Activity.tenant_id == tenant_id,
            Activity.customer_id == customer_id,
            Activity.created_at >= d90,
        )
    )).scalar_one() or 0
    activity_score = min(30, activity_count * 5)

    # 2. Active projects (max 25 pts)
    active_projects = (await db.execute(
        select(func.count()).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.customer_id == customer_id,
            OpportunityProject.is_deleted == False,
            OpportunityProject.stage_code.notin_(["S6", "lost"]),
        )
    )).scalar_one() or 0
    project_score = min(25, active_projects * 10)

    # 3. Payment health (max 25 pts) — ratio of on-time payments
    total_plans = (await db.execute(
        select(func.count()).select_from(PaymentPlan).join(
            OpportunityProject, OpportunityProject.id == PaymentPlan.project_id
        ).where(
            PaymentPlan.tenant_id == tenant_id,
            OpportunityProject.customer_id == customer_id,
            PaymentPlan.is_deleted == False,
        )
    )).scalar_one() or 0
    overdue_plans = (await db.execute(
        select(func.count()).select_from(PaymentPlan).join(
            OpportunityProject, OpportunityProject.id == PaymentPlan.project_id
        ).where(
            PaymentPlan.tenant_id == tenant_id,
            OpportunityProject.customer_id == customer_id,
            PaymentPlan.is_deleted == False,
            PaymentPlan.status == "overdue",
        )
    )).scalar_one() or 0
    if total_plans > 0:
        payment_score = int(25 * (1 - overdue_plans / total_plans))
    else:
        payment_score = 15  # neutral if no plans

    # 4. Service ticket health (max 20 pts) — fewer open tickets = better
    open_tickets = (await db.execute(
        select(func.count()).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.customer_id == customer_id,
            ServiceTicket.is_deleted == False,
            ServiceTicket.status.in_(["open", "in_progress"]),
        )
    )).scalar_one() or 0
    ticket_score = max(0, 20 - open_tickets * 5)

    total = activity_score + project_score + payment_score + ticket_score
    grade = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D"

    return ok({
        "score": total,
        "grade": grade,
        "breakdown": {
            "activity": {"score": activity_score, "max": 30, "detail": f"近90天{activity_count}次互动"},
            "project": {"score": project_score, "max": 25, "detail": f"{active_projects}个活跃商机"},
            "payment": {"score": payment_score, "max": 25, "detail": f"{overdue_plans}/{total_plans}逾期"},
            "service": {"score": ticket_score, "max": 20, "detail": f"{open_tickets}个待处理工单"},
        },
    })
