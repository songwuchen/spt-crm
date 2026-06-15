import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid, async_session_factory
from app.domains.audit.models import AuditLog
from app.common.context import request_ip, request_trace_id, request_user_agent

logger = logging.getLogger("spt_crm.audit")


def _sanitize_for_json(obj):
    """Recursively convert non-JSON-serializable types (Decimal, date, etc.)."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return str(obj)
    return obj


def _compute_content_hash(
    tenant_id: str, user_id: str, action: str, resource_type: str,
    resource_id: str | None, summary: str | None, detail: dict | None,
) -> str:
    """Compute SHA-256 hash of audit log content for tamper detection."""
    payload = f"{tenant_id}|{user_id}|{action}|{resource_type}|{resource_id or ''}|{summary or ''}"
    if detail:
        payload += "|" + json.dumps(detail, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def log_action(
    db: AsyncSession, *, tenant_id: str, user_id: str, user_name: str | None,
    action: str, resource_type: str, resource_id: str | None = None,
    summary: str | None = None, detail: dict | None = None, ip: str | None = None,
):
    """Write a tamper-evidence audit record. **Best-effort, never fatal.**

    Audit logging is a side-effect, not a business invariant. It is written in its
    OWN short-lived session (callers always commit the business change *before*
    logging), so an audit failure can never poison the caller's transaction, expire
    its freshly-loaded objects, or surface a 500 on an already-committed write. The
    ``db`` argument is accepted for signature stability but intentionally not used
    for the write.
    """
    try:
        safe_detail = _sanitize_for_json(detail) if detail else detail
        content_hash = _compute_content_hash(tenant_id, user_id, action, resource_type, resource_id, summary, safe_detail)
        async with async_session_factory() as audit_db:
            audit_db.add(AuditLog(
                id=generate_uuid(), tenant_id=tenant_id,
                user_id=user_id, user_name=user_name,
                action=action, resource_type=resource_type,
                resource_id=resource_id, summary=summary,
                detail=safe_detail,
                ip=ip or request_ip.get(),
                user_agent=request_user_agent.get(),
                trace_id=request_trace_id.get(),
                content_hash=content_hash,
            ))
            await audit_db.commit()
    except Exception:
        logger.warning(
            "audit log_action failed (non-fatal) for %s/%s id=%s",
            resource_type, action, resource_id, exc_info=True,
        )


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
