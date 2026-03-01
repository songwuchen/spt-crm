from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.audit.service import list_audit_logs

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
