"""
AI Proactive Reminders Worker — scans for business conditions that need attention
and generates notifications automatically.

Usage:
    python -m app.workers.reminder_worker

Checks performed each cycle:
  1. Stale projects — no activity for N days at active stages
  2. Upcoming payment due dates — plans due within 7 days
  3. Approval SLA violations — pending tasks exceeding sla_hours
  4. Contracts expiring soon — contracts with end_date within 30 days
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory

logger = logging.getLogger("reminder_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

POLL_INTERVAL = 300  # 5 minutes
STALE_DAYS = 7  # No activity for 7 days = stale
PAYMENT_WARN_DAYS = 7  # Warn 7 days before due
CONTRACT_WARN_DAYS = 30  # Warn 30 days before expiry


async def check_stale_projects(db: AsyncSession) -> int:
    """Find active projects with no recent activity and notify owners."""
    from app.domains.opportunity.models import OpportunityProject
    from app.domains.activity.models import Activity
    from app.domains.notification.service import send_notification

    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    active_stages = ("S1", "S2", "S3", "S4")

    # Get active projects
    projects = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.is_deleted == False,
            OpportunityProject.stage_code.in_(active_stages),
        )
    )).scalars().all()

    notified = 0
    for proj in projects:
        # Check last activity date
        last_activity = (await db.execute(
            select(func.max(Activity.created_at)).where(
                Activity.biz_type == "project",
                Activity.biz_id == proj.id,
            )
        )).scalar()

        is_stale = False
        if last_activity is None:
            # No activity ever — check project creation date
            if proj.created_at and proj.created_at < cutoff:
                is_stale = True
        elif last_activity < cutoff:
            is_stale = True

        if is_stale and proj.owner_id:
            # Avoid duplicate notifications: check if we already sent one recently
            existing = (await db.execute(
                select(func.count()).select_from(
                    select(1).where(
                        and_(
                            _notification_model().tenant_id == proj.tenant_id,
                            _notification_model().recipient_id == proj.owner_id,
                            _notification_model().type == "system",
                            _notification_model().biz_type == "project",
                            _notification_model().biz_id == proj.id,
                            _notification_model().title.like("%跟进停滞%"),
                            _notification_model().created_at > datetime.now(timezone.utc) - timedelta(days=1),
                        )
                    ).subquery()
                )
            )).scalar()

            if existing and existing > 0:
                continue

            days_since = STALE_DAYS
            if last_activity:
                days_since = (datetime.now(timezone.utc) - last_activity).days

            try:
                await send_notification(
                    db=db,
                    tenant_id=proj.tenant_id,
                    recipient_id=proj.owner_id,
                    type="system",
                    title=f"商机跟进停滞提醒: {proj.name}",
                    content=f"商机「{proj.name}」已 {days_since} 天未有跟进活动，当前阶段: {proj.stage_code}，请及时更新。",
                    biz_type="project",
                    biz_id=proj.id,
                )
                notified += 1
            except Exception as e:
                logger.warning(f"Failed to notify stale project {proj.id}: {e}")

    return notified


def _notification_model():
    from app.domains.notification.models import Notification
    return Notification


async def check_upcoming_payments(db: AsyncSession) -> int:
    """Find payment plans due within PAYMENT_WARN_DAYS and notify project owners."""
    from app.domains.payment.models import PaymentPlan
    from app.domains.opportunity.models import OpportunityProject
    from app.domains.notification.service import send_notification

    warn_date = date.today() + timedelta(days=PAYMENT_WARN_DAYS)
    today = date.today()

    plans = (await db.execute(
        select(PaymentPlan).where(
            PaymentPlan.status == "pending",
            PaymentPlan.due_date != None,
            PaymentPlan.due_date <= warn_date,
            PaymentPlan.due_date >= today,
        )
    )).scalars().all()

    notified = 0
    for plan in plans:
        if not plan.project_id:
            continue

        project = (await db.execute(
            select(OpportunityProject).where(OpportunityProject.id == plan.project_id)
        )).scalar_one_or_none()

        if not project or not project.owner_id:
            continue

        days_until = (plan.due_date - today).days
        try:
            await send_notification(
                db=db,
                tenant_id=plan.tenant_id,
                recipient_id=project.owner_id,
                type="payment_overdue",
                title=f"回款计划即将到期: {plan.plan_no}",
                content=f"回款计划「{plan.plan_no}」将在 {days_until} 天后到期（{plan.due_date}），金额: ¥{plan.amount or 0:,.2f}。",
                biz_type="project",
                biz_id=plan.project_id,
            )
            notified += 1
        except Exception as e:
            logger.warning(f"Failed to notify upcoming payment {plan.id}: {e}")

    return notified


async def check_approval_sla(db: AsyncSession) -> int:
    """Find approval tasks that have exceeded their SLA and trigger escalation.

    This function processes all tenants (by design — the worker handles cross-tenant).
    It delegates to the service-level check_sla_overdue which handles escalation chains.
    """
    from app.domains.approval.models import ApprovalFlow
    from app.domains.approval.service import check_sla_overdue

    # Get distinct tenant_ids from pending flows
    tenant_rows = (await db.execute(
        select(ApprovalFlow.tenant_id).where(ApprovalFlow.status == "pending").distinct()
    )).scalars().all()

    notified = 0
    for tid in tenant_rows:
        try:
            count = await check_sla_overdue(db, tid)
            notified += count
        except Exception as e:
            logger.warning(f"SLA check failed for tenant {tid}: {e}")

    return notified


async def check_expiring_contracts(db: AsyncSession) -> int:
    """Find contracts expiring within CONTRACT_WARN_DAYS and notify owners."""
    from app.domains.contract.models import ContractVersion
    from app.domains.opportunity.models import OpportunityProject
    from app.domains.notification.service import send_notification

    warn_date = date.today() + timedelta(days=CONTRACT_WARN_DAYS)
    today = date.today()

    versions = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.status == "signed",
            ContractVersion.end_date != None,
            ContractVersion.end_date <= warn_date,
            ContractVersion.end_date >= today,
        )
    )).scalars().all()

    notified = 0
    for ver in versions:
        if not ver.project_id:
            continue

        project = (await db.execute(
            select(OpportunityProject).where(OpportunityProject.id == ver.project_id)
        )).scalar_one_or_none()

        if not project or not project.owner_id:
            continue

        days_until = (ver.end_date - today).days
        try:
            await send_notification(
                db=db,
                tenant_id=ver.tenant_id,
                recipient_id=project.owner_id,
                type="contract_signed",
                title=f"合同即将到期: {ver.contract_no}",
                content=f"合同「{ver.contract_no}」将在 {days_until} 天后到期（{ver.end_date}），请及时处理续约。",
                biz_type="project",
                biz_id=ver.project_id,
            )
            notified += 1
        except Exception as e:
            logger.warning(f"Failed to notify expiring contract {ver.id}: {e}")

    return notified


async def run_once():
    """Single reminder check cycle."""
    async with async_session_factory() as db:
        stale = await check_stale_projects(db)
        payments = await check_upcoming_payments(db)
        sla = await check_approval_sla(db)
        contracts = await check_expiring_contracts(db)

        total = stale + payments + sla + contracts
        if total > 0:
            logger.info(
                f"Reminders sent: stale_projects={stale}, upcoming_payments={payments}, "
                f"sla_violations={sla}, expiring_contracts={contracts}"
            )
        return total


async def main():
    logger.info("Reminder Worker started. Checking every %ds...", POLL_INTERVAL)
    while True:
        try:
            await run_once()
        except Exception as e:
            logger.error(f"Reminder cycle error: {e}")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
