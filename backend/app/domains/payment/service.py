from datetime import date
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.payment.models import Invoice, PaymentPlan, PaymentRecord
from app.domains.payment.schemas import (
    InvoiceCreate, InvoiceUpdate, PaymentPlanCreate, PaymentPlanUpdate, PaymentRecordCreate,
)
from app.domains.audit.service import log_action


async def mark_overdue_plans(db: AsyncSession, tenant_id: str):
    """Auto-mark pending plans past due_date as overdue."""
    await db.execute(
        update(PaymentPlan).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.status == "pending",
            PaymentPlan.due_date < date.today(),
        ).values(status="overdue")
    )
    await db.commit()


# ==================== Invoice ====================

async def list_invoices(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.project_id == project_id)
        .order_by(Invoice.created_at.desc())
    )
    return result.scalars().all()


async def create_invoice(db: AsyncSession, tenant_id: str, project_id: str, data: InvoiceCreate, user: dict) -> Invoice:
    inv = Invoice(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="invoice", resource_id=inv.id,
                     summary=f"创建发票: {data.invoice_no}")
    return inv


async def update_invoice(db: AsyncSession, tenant_id: str, invoice_id: str, data: InvoiceUpdate, user: dict) -> Invoice:
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not inv:
        raise BusinessException(code=NOT_FOUND, message="发票不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(inv, field, val)
    await db.commit()
    await db.refresh(inv)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="invoice", resource_id=invoice_id,
                     summary=f"更新发票: {inv.invoice_no}")
    return inv


# ==================== PaymentPlan ====================

async def list_plans(db: AsyncSession, tenant_id: str, project_id: str):
    await mark_overdue_plans(db, tenant_id)
    result = await db.execute(
        select(PaymentPlan).where(PaymentPlan.tenant_id == tenant_id, PaymentPlan.project_id == project_id)
        .order_by(PaymentPlan.due_date)
    )
    return result.scalars().all()


async def create_plan(db: AsyncSession, tenant_id: str, project_id: str, data: PaymentPlanCreate, user: dict) -> PaymentPlan:
    plan = PaymentPlan(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        **data.model_dump(exclude_unset=True),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="payment_plan", resource_id=plan.id,
                     summary=f"创建回款计划: {data.plan_no}")
    return plan


async def update_plan(db: AsyncSession, tenant_id: str, plan_id: str, data: PaymentPlanUpdate, user: dict) -> PaymentPlan:
    plan = (await db.execute(
        select(PaymentPlan).where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not plan:
        raise BusinessException(code=NOT_FOUND, message="回款计划不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, val)
    await db.commit()
    await db.refresh(plan)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="payment_plan", resource_id=plan_id,
                     summary=f"更新回款计划: {plan.plan_no}")
    return plan


# ==================== PaymentRecord ====================

async def list_records(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.tenant_id == tenant_id, PaymentRecord.project_id == project_id)
        .order_by(PaymentRecord.received_date.desc())
    )
    return result.scalars().all()


async def create_record(db: AsyncSession, tenant_id: str, project_id: str, data: PaymentRecordCreate, user: dict) -> PaymentRecord:
    rec = PaymentRecord(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)

    # Auto-reconciliation: mark matched plan as paid
    if rec.matched_plan_id:
        plan = (await db.execute(
            select(PaymentPlan).where(PaymentPlan.id == rec.matched_plan_id, PaymentPlan.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if plan and plan.status in ("pending", "overdue"):
            plan.status = "paid"
            await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="payment_record", resource_id=rec.id,
                     summary=f"创建回款记录: ¥{data.amount}")

    # Auto-activity: record payment on project timeline
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "project", project_id, "system",
                              f"收到回款 ¥{float(data.amount):,.2f}", None,
                              user["sub"], user.get("real_name") or user.get("username"))
    except Exception:
        pass

    # Auto-notify project owner
    try:
        from app.domains.project.models import OpportunityProject
        proj = (await db.execute(
            select(OpportunityProject).where(OpportunityProject.id == project_id, OpportunityProject.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if proj and proj.owner_id and proj.owner_id != user["sub"]:
            from app.common.auto_notify import notify_payment_received
            await notify_payment_received(db, tenant_id, float(data.amount), proj.owner_id,
                                           user.get("real_name") or user.get("username"), project_id)
    except Exception:
        pass

    return rec
