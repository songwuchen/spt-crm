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
FOLLOWUP_WARN_DAYS = 1  # Warn 1 day before follow-up date


async def check_stale_projects(db: AsyncSession) -> int:
    """Find active projects with no recent activity and notify owners."""
    from app.domains.project.models import OpportunityProject
    from app.domains.activity.models import Activity
    from app.domains.notification.service import send_notification

    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    active_stages = ("S1", "S2", "S3", "S4")

    # Get active projects (batch limit to prevent OOM)
    projects = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.is_deleted == False,
            OpportunityProject.stage_code.in_(active_stages),
        ).limit(5000)
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
    from app.domains.project.models import OpportunityProject
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
    from app.domains.project.models import OpportunityProject
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


async def check_upcoming_followups(db: AsyncSession) -> int:
    """Notify owners about upcoming follow-up dates."""
    from app.domains.activity.models import Activity
    from app.domains.notification.service import send_notification

    today = date.today()
    warn_date = today + timedelta(days=FOLLOWUP_WARN_DAYS)

    activities = (await db.execute(
        select(Activity).where(
            Activity.next_follow_date >= str(today),
            Activity.next_follow_date <= str(warn_date),
        )
    )).scalars().all()

    notified = 0
    for act in activities:
        if not act.created_by_id:
            continue
        # Skip if already notified
        from app.domains.notification.models import Notification
        existing = (await db.execute(
            select(func.count()).where(
                Notification.tenant_id == act.tenant_id,
                Notification.recipient_id == act.created_by_id,
                Notification.biz_type == "activity",
                Notification.biz_id == act.id,
                Notification.title.like("%跟进提醒%"),
            )
        )).scalar()
        if existing:
            continue

        try:
            await send_notification(
                db=db,
                tenant_id=act.tenant_id,
                recipient_id=act.created_by_id,
                type="stage_change",
                title=f"跟进提醒: {act.subject or '活动'}",
                content=f"您计划在 {act.next_follow_date} 跟进「{act.subject or '活动'}」，请及时处理。",
                biz_type="activity",
                biz_id=act.id,
            )
            notified += 1
        except Exception as e:
            logger.warning(f"Failed to notify follow-up {act.id}: {e}")

    return notified


async def check_pool_auto_release(db: AsyncSession) -> int:
    """Auto-release customers to pool based on tenant pool rules.

    Pool rules stored in TenantProfile.security_policy_json:
      {"pool_rules": {"enabled": true, "idle_days": {"A": 90, "B": 60, "C": 30, "D": 15}, "default_idle_days": 30}}
    """
    from app.domains.customer.models import Customer
    from app.domains.activity.models import Activity
    from app.domains.admin.models import TenantProfile
    from app.domains.notification.service import send_notification

    profiles = (await db.execute(
        select(TenantProfile)
    )).scalars().all()

    released = 0
    for profile in profiles:
        policy = (profile.security_policy_json or {}).get("pool_rules")
        if not policy or not policy.get("enabled"):
            continue

        idle_by_level = policy.get("idle_days", {})
        default_idle = policy.get("default_idle_days", 30)

        # Get active customers with owners (batch limit)
        customers = (await db.execute(
            select(Customer).where(
                Customer.tenant_id == profile.tenant_id,
                Customer.status == "active",
                Customer.is_deleted == False,
                Customer.owner_id != None,
            ).limit(5000)
        )).scalars().all()

        for cust in customers:
            idle_days = idle_by_level.get(cust.level or "D", default_idle)
            cutoff = datetime.now(timezone.utc) - timedelta(days=idle_days)

            # Check last activity
            last = (await db.execute(
                select(func.max(Activity.created_at)).where(
                    Activity.biz_type == "customer",
                    Activity.biz_id == cust.id,
                )
            )).scalar()

            is_idle = False
            if last is None and cust.created_at and cust.created_at < cutoff:
                is_idle = True
            elif last and last < cutoff:
                is_idle = True

            if is_idle:
                old_owner = cust.owner_id
                cust.status = "pool"
                cust.owner_id = None
                cust.owner_name = None
                released += 1

                if old_owner:
                    try:
                        await send_notification(
                            db=db, tenant_id=profile.tenant_id,
                            recipient_id=old_owner,
                            type="system",
                            title=f"客户自动释放到公海: {cust.name}",
                            content=f"客户「{cust.name}」因 {idle_days} 天无跟进活动已自动释放到公海池。",
                            biz_type="customer", biz_id=cust.id,
                        )
                    except Exception:
                        pass

    if released > 0:
        await db.commit()
        logger.info(f"Auto-released {released} idle customers to pool")
    return released


AUDIT_RETENTION_DAYS = 180  # Keep audit logs for 6 months


async def cleanup_old_audit_logs(db: AsyncSession) -> int:
    """Delete audit logs older than retention period."""
    from sqlalchemy import delete as sql_delete
    from app.domains.audit.models import AuditLog

    cutoff = datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)
    result = await db.execute(
        sql_delete(AuditLog).where(AuditLog.created_at < cutoff)
    )
    if result.rowcount > 0:
        await db.commit()
        logger.info(f"Cleaned up {result.rowcount} old audit log entries (>{AUDIT_RETENTION_DAYS} days)")
    return result.rowcount


async def cleanup_old_notifications(db: AsyncSession) -> int:
    """Delete read notifications older than 90 days."""
    from sqlalchemy import delete as sql_delete
    _Notification = _notification_model()

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    result = await db.execute(
        sql_delete(_Notification).where(
            _Notification.is_read == True,
            _Notification.created_at < cutoff,
        )
    )
    if result.rowcount > 0:
        await db.commit()
        logger.info(f"Cleaned up {result.rowcount} old read notifications (>90 days)")
    return result.rowcount


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Deactivate expired login sessions."""
    from sqlalchemy import update as sql_update
    from app.domains.auth.models import LoginSession

    result = await db.execute(
        sql_update(LoginSession).where(
            LoginSession.is_active == True,
            LoginSession.expired_at != None,
            LoginSession.expired_at < datetime.now(timezone.utc),
        ).values(is_active=False)
    )
    if result.rowcount > 0:
        await db.commit()
        logger.info(f"Deactivated {result.rowcount} expired login sessions")
    return result.rowcount


async def cleanup_soft_deleted_records(db: AsyncSession) -> int:
    """Delete soft-deleted records older than 30 days across key tables."""
    from sqlalchemy import delete as sql_delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    total = 0

    # Import models that support soft delete
    from app.domains.customer.models import Customer
    from app.domains.lead.models import Lead
    from app.domains.project.models import OpportunityProject

    for model in [Customer, Lead, OpportunityProject]:
        try:
            result = await db.execute(
                sql_delete(model).where(
                    model.is_deleted == True,
                    model.updated_at < cutoff,
                )
            )
            total += result.rowcount
        except Exception as e:
            logger.warning(f"Failed to clean {model.__tablename__}: {e}")

    if total > 0:
        await db.commit()
        logger.info(f"Purged {total} soft-deleted records older than 30 days")
    return total


async def cleanup_old_outbox_events(db: AsyncSession) -> int:
    """Delete published/failed outbox events older than 90 days."""
    from sqlalchemy import delete as sql_delete
    from app.domains.outbox.models import OutboxEvent

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    result = await db.execute(
        sql_delete(OutboxEvent).where(
            OutboxEvent.status.in_(["published", "failed"]),
            OutboxEvent.updated_at < cutoff,
        )
    )
    if result.rowcount > 0:
        await db.commit()
        logger.info(f"Cleaned up {result.rowcount} old outbox events (>90 days)")
    return result.rowcount


async def cleanup_inactive_sessions(db: AsyncSession) -> int:
    """Hard-delete inactive login sessions older than 90 days."""
    from sqlalchemy import delete as sql_delete
    from app.domains.auth.models import LoginSession

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    result = await db.execute(
        sql_delete(LoginSession).where(
            LoginSession.is_active == False,
            LoginSession.updated_at < cutoff,
        )
    )
    if result.rowcount > 0:
        await db.commit()
        logger.info(f"Purged {result.rowcount} inactive login sessions (>90 days)")
    return result.rowcount


async def check_scheduled_reports(db: AsyncSession) -> int:
    """Send scheduled report emails based on tenant report_schedules config."""
    from app.domains.admin.models import TenantProfile
    from app.domains.notification.service import send_notification

    now = datetime.now(timezone.utc)
    current_hour = now.hour
    current_weekday = now.weekday()  # 0=Mon
    current_day = now.day

    profiles = (await db.execute(select(TenantProfile))).scalars().all()
    total = 0

    for profile in profiles:
        policy = profile.security_policy_json or {}
        schedules = policy.get("report_schedules", [])
        if not schedules:
            continue

        for sched in schedules:
            if not sched.get("enabled", True):
                continue
            freq = sched.get("frequency", "daily")
            send_hour = sched.get("send_hour", 8)

            if current_hour != send_hour:
                continue
            if freq == "weekly" and current_weekday != sched.get("send_weekday", 0):
                continue
            if freq == "monthly" and current_day != sched.get("send_day", 1):
                continue

            report_type = sched.get("report_type", "summary")
            recipients = sched.get("recipient_ids", [])

            for uid in recipients:
                await send_notification(
                    db, profile.tenant_id, uid,
                    type="scheduled_report",
                    title=f"定时报表: {sched.get('name', report_type)}",
                    content=f"您订阅的{freq_label(freq)}报表已生成，请前往报表中心查看。",
                    biz_type="report",
                    extra_json={"report_type": report_type, "frequency": freq},
                )
                total += 1

    return total


def freq_label(freq: str) -> str:
    return {"daily": "每日", "weekly": "每周", "monthly": "每月"}.get(freq, freq)


async def run_once():
    """Single reminder check cycle."""
    async with async_session_factory() as db:
        stale = await check_stale_projects(db)
        payments = await check_upcoming_payments(db)
        sla = await check_approval_sla(db)
        contracts = await check_expiring_contracts(db)
        audit_cleanup = await cleanup_old_audit_logs(db)
        notif_cleanup = await cleanup_old_notifications(db)
        session_cleanup = await cleanup_expired_sessions(db)
        deleted_cleanup = await cleanup_soft_deleted_records(db)
        outbox_cleanup = await cleanup_old_outbox_events(db)
        inactive_sessions = await cleanup_inactive_sessions(db)

        followups = await check_upcoming_followups(db)
        pool_released = await check_pool_auto_release(db)
        reports = await check_scheduled_reports(db)
        total = stale + payments + sla + contracts + followups + pool_released + reports
        if total > 0:
            logger.info(
                f"Reminders sent: stale_projects={stale}, upcoming_payments={payments}, "
                f"sla_violations={sla}, expiring_contracts={contracts}, followups={followups}, pool_released={pool_released}, reports={reports}"
            )
        cleanup_total = audit_cleanup + notif_cleanup + session_cleanup + deleted_cleanup + outbox_cleanup + inactive_sessions
        if cleanup_total > 0:
            logger.info(f"Cleanup: audit={audit_cleanup}, notif={notif_cleanup}, sessions={session_cleanup}, deleted={deleted_cleanup}, outbox={outbox_cleanup}, inactive_sessions={inactive_sessions}")
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
