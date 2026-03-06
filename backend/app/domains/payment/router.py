from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.payment import service
from app.domains.payment.models import PaymentPlan, PaymentRecord, Invoice
from app.domains.payment.schemas import (
    InvoiceCreate, InvoiceUpdate, PaymentPlanCreate, PaymentPlanUpdate, PaymentRecordCreate,
)
from app.domains.project.models import OpportunityProject

router = APIRouter(tags=["回款管理"])


def _inv_dict(i) -> dict:
    return {
        "id": i.id, "project_id": i.project_id,
        "invoice_no": i.invoice_no,
        "amount": float(i.amount) if i.amount is not None else None,
        "invoice_date": str(i.invoice_date) if i.invoice_date else None,
        "status": i.status, "erp_ref_json": i.erp_ref_json, "remark": i.remark,
        "created_by_id": i.created_by_id, "created_by_name": i.created_by_name,
        "created_at": i.created_at.isoformat() if i.created_at else "",
    }


def _plan_dict(p) -> dict:
    return {
        "id": p.id, "project_id": p.project_id,
        "plan_no": p.plan_no,
        "due_date": str(p.due_date) if p.due_date else None,
        "amount": float(p.amount) if p.amount is not None else None,
        "trigger_milestone_code": p.trigger_milestone_code,
        "status": p.status, "remark": p.remark,
        "created_at": p.created_at.isoformat() if p.created_at else "",
    }


def _rec_dict(r) -> dict:
    return {
        "id": r.id, "project_id": r.project_id,
        "received_date": str(r.received_date) if r.received_date else None,
        "amount": float(r.amount) if r.amount is not None else None,
        "channel": r.channel, "reference_no": r.reference_no,
        "matched_plan_id": r.matched_plan_id, "remark": r.remark,
        "created_by_id": r.created_by_id, "created_by_name": r.created_by_name,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


# --- Invoice ---

@router.get("/api/v1/projects/{project_id}/invoices")
async def list_invoices(
    project_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("payment:view")),
):
    items = await service.list_invoices(db, tenant_id, project_id)
    return ok([_inv_dict(i) for i in items])


@router.post("/api/v1/projects/{project_id}/invoices")
async def create_invoice(
    project_id: str, body: InvoiceCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("payment:edit")),
):
    inv = await service.create_invoice(db, tenant_id, project_id, body, current_user)
    return ok(_inv_dict(inv))


@router.put("/api/v1/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str, body: InvoiceUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("payment:edit")),
):
    inv = await service.update_invoice(db, tenant_id, invoice_id, body, current_user)
    return ok(_inv_dict(inv))


# --- PaymentPlan ---

@router.get("/api/v1/projects/{project_id}/payment_plans")
async def list_plans(
    project_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("payment:view")),
):
    items = await service.list_plans(db, tenant_id, project_id)
    return ok([_plan_dict(p) for p in items])


@router.post("/api/v1/projects/{project_id}/payment_plans")
async def create_plan(
    project_id: str, body: PaymentPlanCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("payment:edit")),
):
    plan = await service.create_plan(db, tenant_id, project_id, body, current_user)
    return ok(_plan_dict(plan))


@router.put("/api/v1/payment_plans/{plan_id}")
async def update_plan(
    plan_id: str, body: PaymentPlanUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("payment:edit")),
):
    plan = await service.update_plan(db, tenant_id, plan_id, body, current_user)
    return ok(_plan_dict(plan))


# --- PaymentRecord ---

@router.get("/api/v1/projects/{project_id}/payment_records")
async def list_records(
    project_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("payment:view")),
):
    items = await service.list_records(db, tenant_id, project_id)
    return ok([_rec_dict(r) for r in items])


@router.post("/api/v1/projects/{project_id}/payment_records")
async def create_record(
    project_id: str, body: PaymentRecordCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("payment:edit")),
):
    rec = await service.create_record(db, tenant_id, project_id, body, current_user)
    return ok(_rec_dict(rec))


# --- Cross-project listing ---

@router.get("/api/v1/payment/plans")
async def list_all_plans(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("payment:view")),
):
    """List all payment plans across projects with pagination."""
    q = select(
        PaymentPlan, OpportunityProject.name.label("project_name"),
        OpportunityProject.project_code.label("project_code"),
    ).outerjoin(OpportunityProject, OpportunityProject.id == PaymentPlan.project_id).where(
        PaymentPlan.tenant_id == tenant_id
    )
    count_q = select(func.count(PaymentPlan.id)).where(PaymentPlan.tenant_id == tenant_id)

    if status:
        q = q.where(PaymentPlan.status == status)
        count_q = count_q.where(PaymentPlan.status == status)
    if keyword:
        kw = f"%{keyword}%"
        flt = or_(PaymentPlan.plan_no.ilike(kw), PaymentPlan.remark.ilike(kw))
        q = q.where(flt)
        count_q = count_q.where(flt)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        q.order_by(PaymentPlan.due_date.asc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).all()

    items = []
    for row in rows:
        plan = row[0]
        d = _plan_dict(plan)
        d["project_name"] = row.project_name
        d["project_code"] = row.project_code
        items.append(d)

    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/api/v1/payment/records")
async def list_all_records(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("payment:view")),
):
    """List all payment records across projects with pagination."""
    q = select(
        PaymentRecord, OpportunityProject.name.label("project_name"),
        OpportunityProject.project_code.label("project_code"),
    ).outerjoin(OpportunityProject, OpportunityProject.id == PaymentRecord.project_id).where(
        PaymentRecord.tenant_id == tenant_id
    )
    count_q = select(func.count(PaymentRecord.id)).where(PaymentRecord.tenant_id == tenant_id)

    if keyword:
        kw = f"%{keyword}%"
        flt = or_(PaymentRecord.reference_no.ilike(kw), PaymentRecord.channel.ilike(kw), PaymentRecord.remark.ilike(kw))
        q = q.where(flt)
        count_q = count_q.where(flt)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        q.order_by(PaymentRecord.received_date.desc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).all()

    items = []
    for row in rows:
        rec = row[0]
        d = _rec_dict(rec)
        d["project_name"] = row.project_name
        d["project_code"] = row.project_code
        items.append(d)

    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/api/v1/payment/invoices")
async def list_all_invoices(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("payment:view")),
):
    """List all invoices across projects with pagination."""
    q = select(
        Invoice, OpportunityProject.name.label("project_name"),
        OpportunityProject.project_code.label("project_code"),
    ).outerjoin(OpportunityProject, OpportunityProject.id == Invoice.project_id).where(
        Invoice.tenant_id == tenant_id
    )
    count_q = select(func.count(Invoice.id)).where(Invoice.tenant_id == tenant_id)

    if status:
        q = q.where(Invoice.status == status)
        count_q = count_q.where(Invoice.status == status)
    if keyword:
        kw = f"%{keyword}%"
        flt = or_(Invoice.invoice_no.ilike(kw), Invoice.remark.ilike(kw))
        q = q.where(flt)
        count_q = count_q.where(flt)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        q.order_by(Invoice.created_at.desc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).all()

    items = []
    for row in rows:
        inv = row[0]
        d = _inv_dict(inv)
        d["project_name"] = row.project_name
        d["project_code"] = row.project_code
        items.append(d)

    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/api/v1/payment/check_overdue")
async def check_overdue(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("payment:view")),
):
    """Manually trigger overdue check and notifications. Can also be called by cron/worker."""
    notified = await service.check_overdue_and_notify(db, tenant_id)
    return ok({"notified_projects": notified})
