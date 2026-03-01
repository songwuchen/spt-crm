from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.payment import service
from app.domains.payment.schemas import (
    InvoiceCreate, InvoiceUpdate, PaymentPlanCreate, PaymentPlanUpdate, PaymentRecordCreate,
)

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
