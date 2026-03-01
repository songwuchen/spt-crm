from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.change.models import ChangeRequest
from app.domains.change.schemas import ChangeRequestCreate, ChangeRequestUpdate
from app.domains.audit.service import log_action


def _generate_change_no() -> str:
    now = datetime.now(timezone.utc)
    import random
    seq = random.randint(1000, 9999)
    return f"CR-{now.strftime('%Y%m%d')}-{seq}"


async def list_by_project(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(ChangeRequest).where(ChangeRequest.tenant_id == tenant_id, ChangeRequest.project_id == project_id)
        .order_by(ChangeRequest.created_at.desc())
    )
    return result.scalars().all()


async def get(db: AsyncSession, tenant_id: str, cr_id: str) -> ChangeRequest:
    cr = (await db.execute(
        select(ChangeRequest).where(ChangeRequest.id == cr_id, ChangeRequest.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not cr:
        raise BusinessException(code=NOT_FOUND, message="变更单不存在")
    return cr


async def create(db: AsyncSession, tenant_id: str, project_id: str, data: ChangeRequestCreate, user: dict) -> ChangeRequest:
    cr = ChangeRequest(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        change_no=_generate_change_no(),
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(cr)
    await db.commit()
    await db.refresh(cr)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="change_request", resource_id=cr.id,
                     summary=f"创建变更单: {cr.change_no}")
    return cr


VALID_STATUS_TRANSITIONS = {
    "draft": {"reviewing"},
    "reviewing": {"approved", "rejected"},
    "approved": {"implemented"},
    "rejected": {"draft"},
    "implemented": set(),
}


async def update(db: AsyncSession, tenant_id: str, cr_id: str, data: ChangeRequestUpdate, user: dict) -> ChangeRequest:
    cr = await get(db, tenant_id, cr_id)
    update_data = data.model_dump(exclude_unset=True)
    # Validate status transition
    new_status = update_data.get("status")
    if new_status and new_status != cr.status:
        allowed = VALID_STATUS_TRANSITIONS.get(cr.status, set())
        if new_status not in allowed:
            raise BusinessException(
                code=42200,
                message=f"变更单状态不能从 {cr.status} 变为 {new_status}，允许: {', '.join(allowed) if allowed else '无'}",
            )
    for field, val in update_data.items():
        setattr(cr, field, val)
    await db.commit()
    await db.refresh(cr)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="change_request", resource_id=cr_id,
                     summary=f"更新变更单: {cr.change_no} → {cr.status}")

    # Auto-activity: record status change on project timeline
    if new_status and new_status != cr.status:
        try:
            from app.common.auto_activity import record_activity
            status_labels = {"draft": "草稿", "reviewing": "评审中", "approved": "已批准", "rejected": "已驳回", "implemented": "已实施"}
            await record_activity(db, tenant_id, "project", cr.project_id, "system",
                                  f"变更单 {cr.change_no} 状态: {status_labels.get(cr.status, cr.status)}", None,
                                  user["sub"], user.get("real_name") or user.get("username"))
        except Exception:
            pass

    return cr


async def delete(db: AsyncSession, tenant_id: str, cr_id: str, user: dict):
    cr = await get(db, tenant_id, cr_id)
    await db.delete(cr)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="change_request", resource_id=cr_id,
                     summary=f"删除变更单: {cr.change_no}")
