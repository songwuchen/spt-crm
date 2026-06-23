import logging
from datetime import date
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, DUPLICATE_ENTRY
from app.domains.payment.models import Invoice, PaymentPlan, PaymentRecord
from app.domains.payment.schemas import (
    InvoiceCreate, InvoiceUpdate, PaymentPlanCreate, PaymentPlanUpdate, PaymentRecordCreate,
)
from app.domains.payment.schemas import PaymentPlanBulkCreate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code

logger = logging.getLogger("spt_crm.payment")


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


async def check_overdue_and_notify(db: AsyncSession, tenant_id: str):
    """Check overdue payment plans and create notifications for project owners."""
    await mark_overdue_plans(db, tenant_id)

    # Find all overdue plans
    overdue_result = await db.execute(
        select(PaymentPlan).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.status == "overdue",
        )
    )
    overdue_plans = overdue_result.scalars().all()
    if not overdue_plans:
        return 0

    # Group by project
    from collections import defaultdict
    project_plans: dict[str, list] = defaultdict(list)
    for p in overdue_plans:
        project_plans[p.project_id].append(p)

    # Get project owners
    from app.domains.project.models import OpportunityProject
    project_ids = list(project_plans.keys())
    proj_result = await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.id.in_(project_ids),
            OpportunityProject.tenant_id == tenant_id,
        )
    )
    projects = {p.id: p for p in proj_result.scalars().all()}

    # Send notifications
    from app.domains.notification.service import send_notification
    notified = 0
    for project_id, plans in project_plans.items():
        if not project_id:
            continue
        proj = projects.get(project_id)
        if not proj or not proj.owner_id:
            continue
        total_overdue = sum(float(p.amount) for p in plans if p.amount)
        plan_count = len(plans)
        try:
            await send_notification(
                db, tenant_id,
                recipient_id=proj.owner_id,
                type="payment_overdue",
                title=f"回款逾期提醒: {proj.name}",
                content=f"商机「{proj.name}」有 {plan_count} 笔回款计划已逾期，逾期总额 ¥{total_overdue:,.2f}",
                biz_type="project",
                biz_id=project_id,
                sender_name="系统",
            )
            notified += 1
        except Exception as e:
            logger.warning("Payment overdue notification failed for project %s: %s", project_id, e)

    return notified


# ==================== Invoice ====================

async def list_invoices(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.project_id == project_id)
        .order_by(Invoice.created_at.desc())
    )
    return result.scalars().all()


async def create_invoice(db: AsyncSession, tenant_id: str, project_id: str, data: InvoiceCreate, user: dict) -> Invoice:
    dump = data.model_dump(exclude_unset=True)
    if not dump.get("invoice_no"):
        dump["invoice_no"] = await generate_code(db, tenant_id, "invoice")
    inv = Invoice(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **dump,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="invoice", resource_id=inv.id,
                     summary=f"创建发票: {inv.invoice_no}")
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


async def delete_invoice(db: AsyncSession, tenant_id: str, invoice_id: str, user: dict):
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not inv:
        raise BusinessException(code=NOT_FOUND, message="发票不存在")
    await db.delete(inv)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="invoice", resource_id=invoice_id,
                     summary=f"删除发票: {inv.invoice_no}")


# ==================== PaymentPlan ====================

async def list_plans(db: AsyncSession, tenant_id: str, project_id: str):
    await mark_overdue_plans(db, tenant_id)
    result = await db.execute(
        select(PaymentPlan).where(PaymentPlan.tenant_id == tenant_id, PaymentPlan.project_id == project_id)
        .order_by(PaymentPlan.due_date)
    )
    return result.scalars().all()


async def create_plan(db: AsyncSession, tenant_id: str, project_id: str, data: PaymentPlanCreate, user: dict) -> PaymentPlan:
    dump = data.model_dump(exclude_unset=True)
    if not dump.get("plan_no"):
        dump["plan_no"] = await generate_code(db, tenant_id, "payment_plan")
    plan = PaymentPlan(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        **dump,
    )
    db.add(plan)
    try:
        await db.commit()
    except IntegrityError:
        # uq_plan_tenant_no protects (tenant_id, plan_no) — a reused plan number
        # should be a clean validation error, not a 500.
        await db.rollback()
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"回款计划编号 {dump.get('plan_no')} 已存在，请换一个编号")
    await db.refresh(plan)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="payment_plan", resource_id=plan.id,
                     summary=f"创建回款计划: {plan.plan_no}")
    return plan


async def bulk_create_plans(
    db: AsyncSession, tenant_id: str, project_id: str, data: PaymentPlanBulkCreate, user: dict
) -> list[PaymentPlan]:
    """Create multiple payment plans in one atomic transaction.

    Used by the contract detail page to turn a contract's payment terms into
    回款计划 in one shot. generate_code only flushes (no commit), so the whole
    batch shares a single commit.
    """
    # 覆盖重生成：先删除本合同上次生成的计划（仅限同项目+同来源合同）
    deleted = 0
    if data.replace_existing and data.source_contract_id:
        existing = (await db.execute(
            select(PaymentPlan).where(
                PaymentPlan.tenant_id == tenant_id,
                PaymentPlan.project_id == project_id,
                PaymentPlan.source_contract_id == data.source_contract_id,
            )
        )).scalars().all()
        for p in existing:
            await db.delete(p)
            deleted += 1

    plans: list[PaymentPlan] = []
    for item in data.plans:
        dump = item.model_dump(exclude_unset=True)
        if not dump.get("plan_no"):
            dump["plan_no"] = await generate_code(db, tenant_id, "payment_plan")
        plan = PaymentPlan(
            id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
            source_contract_id=data.source_contract_id, **dump,
        )
        db.add(plan)
        plans.append(plan)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessException(code=DUPLICATE_ENTRY,
                                message="回款计划编号重复，请确保每条计划编号唯一")
    for plan in plans:
        await db.refresh(plan)
    if plans or deleted:
        summary = f"批量生成回款计划: {len(plans)} 条"
        if deleted:
            summary += f"（覆盖删除 {deleted} 条）"
        await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                         action="create", resource_type="payment_plan", resource_id=project_id,
                         summary=summary)
    return plans


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


async def delete_plan(db: AsyncSession, tenant_id: str, plan_id: str, user: dict):
    plan = (await db.execute(
        select(PaymentPlan).where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not plan:
        raise BusinessException(code=NOT_FOUND, message="回款计划不存在")
    await db.delete(plan)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="payment_plan", resource_id=plan_id,
                     summary=f"删除回款计划: {plan.plan_no}")


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
    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.payment.received", "payment", rec.id, {
        "payment_record_id": rec.id, "project_id": project_id,
        "amount": float(data.amount) if data.amount is not None else None,
    })
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
    except Exception as e:
        logger.warning("Auto-activity record for payment received failed: %s", e)

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
    except Exception as e:
        logger.warning("Auto-notify project owner for payment received failed: %s", e)

    return rec


async def delete_record(db: AsyncSession, tenant_id: str, record_id: str, user: dict):
    rec = (await db.execute(
        select(PaymentRecord).where(PaymentRecord.id == record_id, PaymentRecord.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rec:
        raise BusinessException(code=NOT_FOUND, message="回款记录不存在")
    await db.delete(rec)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="payment_record", resource_id=record_id,
                     summary=f"删除回款记录: ¥{float(rec.amount) if rec.amount else 0}")
