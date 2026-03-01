from datetime import date, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.domains.audit.models import AuditLog
from app.common.context import request_ip, request_trace_id, request_user_agent


async def log_action(
    db: AsyncSession, *, tenant_id: str, user_id: str, user_name: str | None,
    action: str, resource_type: str, resource_id: str | None = None,
    summary: str | None = None, detail: dict | None = None, ip: str | None = None,
):
    log = AuditLog(
        id=generate_uuid(), tenant_id=tenant_id,
        user_id=user_id, user_name=user_name,
        action=action, resource_type=resource_type,
        resource_id=resource_id, summary=summary,
        detail=detail,
        ip=ip or request_ip.get(),
        user_agent=request_user_agent.get(),
        trace_id=request_trace_id.get(),
    )
    db.add(log)
    await db.commit()


async def list_audit_logs(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    resource_type: str | None = None, action: str | None = None, user_id: str | None = None,
    keyword: str | None = None, start_date: date | None = None, end_date: date | None = None,
):
    base = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if resource_type:
        base = base.where(AuditLog.resource_type == resource_type)
    if action:
        base = base.where(AuditLog.action == action)
    if user_id:
        base = base.where(AuditLog.user_id == user_id)
    if keyword:
        base = base.where(
            AuditLog.user_name.ilike(f"%{keyword}%") | AuditLog.summary.ilike(f"%{keyword}%")
        )
    if start_date:
        base = base.where(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        base = base.where(AuditLog.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(AuditLog.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total
