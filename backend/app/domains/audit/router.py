from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.audit.service import list_audit_logs
from app.domains.audit.models import AuditLog

router = APIRouter(prefix="/api/v1/audit_logs", tags=["审计日志"])


@router.get("")
async def list_logs(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    resource_type: str = Query(None),
    action: str = Query(None),
    user_id: str = Query(None),
    keyword: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("audit:view")),
):
    items, total = await list_audit_logs(
        db, tenant_id, pageNo, pageSize,
        resource_type, action, user_id, keyword, start_date, end_date,
    )
    logs = []
    for log in items:
        logs.append({
            "id": log.id, "user_id": log.user_id, "user_name": log.user_name,
            "action": log.action, "resource_type": log.resource_type,
            "resource_id": log.resource_id, "summary": log.summary,
            "detail": log.detail, "ip": log.ip,
            "created_at": log.created_at.isoformat() if log.created_at else "",
        })
    return ok({"items": logs, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/statistics")
async def statistics(
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("audit:view")),
):
    """Audit log statistics: action/resource distribution, daily activity, top operators."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base = select(AuditLog).where(
        AuditLog.tenant_id == tenant_id,
        AuditLog.created_at >= since,
    )

    # Total count
    total = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= since,
        )
    )).scalar() or 0

    # By action
    action_rows = (await db.execute(
        select(AuditLog.action, func.count(AuditLog.id).label("cnt")).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= since,
        ).group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc())
    )).all()
    by_action = [{"action": r.action, "count": r.cnt} for r in action_rows]

    # By resource type
    resource_rows = (await db.execute(
        select(AuditLog.resource_type, func.count(AuditLog.id).label("cnt")).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= since,
        ).group_by(AuditLog.resource_type).order_by(func.count(AuditLog.id).desc())
    )).all()
    by_resource = [{"resource_type": r.resource_type, "count": r.cnt} for r in resource_rows]

    # Daily activity (last N days)
    daily_rows = (await db.execute(
        select(
            func.date(AuditLog.created_at).label("day"),
            func.count(AuditLog.id).label("cnt"),
        ).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= since,
        ).group_by(func.date(AuditLog.created_at))
        .order_by(func.date(AuditLog.created_at))
    )).all()
    daily = [{"date": str(r.day), "count": r.cnt} for r in daily_rows]

    # Top operators
    operator_rows = (await db.execute(
        select(
            AuditLog.user_id, AuditLog.user_name,
            func.count(AuditLog.id).label("cnt"),
        ).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= since,
        ).group_by(AuditLog.user_id, AuditLog.user_name)
        .order_by(func.count(AuditLog.id).desc()).limit(10)
    )).all()
    top_operators = [{"user_id": r.user_id, "user_name": r.user_name or "未知", "count": r.cnt} for r in operator_rows]

    return ok({
        "total": total,
        "days": days,
        "by_action": by_action,
        "by_resource": by_resource,
        "daily": daily,
        "top_operators": top_operators,
    })


@router.get("/export")
async def export_logs(
    start_date: date = Query(None),
    end_date: date = Query(None),
    resource_type: str = Query(None),
    action: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("audit:view")),
):
    """Export audit logs as Excel."""
    items, _ = await list_audit_logs(
        db, tenant_id, page_no=1, page_size=10000,
        resource_type=resource_type, action=action,
        start_date=start_date, end_date=end_date,
    )
    headers = ["时间", "操作人", "动作", "资源类型", "资源ID", "摘要", "IP"]
    rows = []
    for log in items:
        rows.append([
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
            log.user_name or "",
            log.action or "",
            log.resource_type or "",
            log.resource_id or "",
            log.summary or "",
            log.ip or "",
        ])
    buf = build_excel("审计日志", headers, rows)
    filename = f"audit_logs_{start_date or 'all'}_{end_date or 'all'}.xlsx"
    return excel_response(buf, filename)


@router.post("/verify")
async def verify_integrity(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("audit:view")),
):
    """Verify audit log integrity by re-computing content hashes."""
    from app.domains.audit.service import _compute_content_hash
    items, _ = await list_audit_logs(db, tenant_id, page_no=1, page_size=10000)
    total = len(items)
    tampered = []
    no_hash = 0
    for log in items:
        if not log.content_hash:
            no_hash += 1
            continue
        expected = _compute_content_hash(
            log.tenant_id, log.user_id, log.action, log.resource_type,
            log.resource_id, log.summary, log.detail,
        )
        if expected != log.content_hash:
            tampered.append({
                "id": log.id,
                "created_at": log.created_at.isoformat() if log.created_at else "",
                "summary": log.summary,
            })
    return ok({
        "total_checked": total,
        "no_hash": no_hash,
        "tampered_count": len(tampered),
        "tampered": tampered[:50],
    })
