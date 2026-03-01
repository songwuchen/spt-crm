from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.activity.models import Activity
from app.domains.activity.schemas import ActivityCreate, ActivityUpdate
from app.domains.audit.service import log_action


async def list_activities(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str):
    result = await db.execute(
        select(Activity).where(
            Activity.tenant_id == tenant_id,
            Activity.biz_type == biz_type,
            Activity.biz_id == biz_id,
        ).order_by(Activity.created_at.desc())
    )
    return result.scalars().all()


async def get_activity(db: AsyncSession, tenant_id: str, activity_id: str) -> Activity:
    a = (await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not a:
        raise BusinessException(code=NOT_FOUND, message="活动记录不存在")
    return a


async def create_activity(db: AsyncSession, tenant_id: str, data: ActivityCreate, user: dict) -> Activity:
    activity = Activity(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"],
        created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="create", resource_type="activity", resource_id=activity.id,
        summary=f"添加互动记录: {data.activity_type} - {data.subject or ''}"
    )
    return activity


async def update_activity(db: AsyncSession, tenant_id: str, activity_id: str, data: ActivityUpdate, user: dict) -> Activity:
    activity = await get_activity(db, tenant_id, activity_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(activity, field, val)
    await db.commit()
    await db.refresh(activity)
    return activity


async def delete_activity(db: AsyncSession, tenant_id: str, activity_id: str):
    activity = await get_activity(db, tenant_id, activity_id)
    await db.delete(activity)
    await db.commit()
