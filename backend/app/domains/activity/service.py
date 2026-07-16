from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.activity.models import Activity
from app.domains.activity.schemas import ActivityCreate, ActivityUpdate
from app.domains.audit.service import log_action


async def list_activities(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str, limit: int = 50, offset: int = 0):
    result = await db.execute(
        select(Activity).where(
            Activity.tenant_id == tenant_id,
            Activity.biz_type == biz_type,
            Activity.biz_id == biz_id,
        ).order_by(Activity.created_at.desc()).offset(offset).limit(limit)
    )
    return result.scalars().all()


async def get_activity(db: AsyncSession, tenant_id: str, activity_id: str) -> Activity:
    a = (await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not a:
        raise BusinessException(code=NOT_FOUND, message="活动记录不存在")
    return a


async def _sync_customer_last_activity(db: AsyncSession, tenant_id: str, customer_id: str):
    """按现存活动重算客户「最新跟进人/时间」冗余；删除(尤其是最新)活动后调用，
    避免残留过期值让客户显得比实际更近被跟进、从而延迟自动回收。"""
    from app.domains.customer.models import Customer
    latest = (await db.execute(
        select(Activity).where(
            Activity.tenant_id == tenant_id,
            Activity.biz_type == "customer",
            Activity.biz_id == customer_id,
        ).order_by(Activity.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    cust = (await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not cust:
        return
    cust.last_activity_at = latest.created_at if latest else None
    cust.last_activity_by_id = latest.created_by_id if latest else None
    cust.last_activity_by_name = latest.created_by_name if latest else None
    await db.commit()


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

    # 冗余「最新跟进人/最新活动时间」到客户，驱动列表「N天未跟进」展示与公海自动回收
    if activity.biz_type == "customer":
        try:
            from app.domains.customer.models import Customer
            cust = (await db.execute(
                select(Customer).where(Customer.id == activity.biz_id, Customer.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cust:
                cust.last_activity_at = activity.created_at
                cust.last_activity_by_id = activity.created_by_id
                cust.last_activity_by_name = activity.created_by_name
                await db.commit()
        except Exception:
            pass  # 冗余失败不阻断主流程

    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="create", resource_type="activity", resource_id=activity.id,
        summary=f"添加互动记录: {data.activity_type} - {data.subject or ''}"
    )

    # Send @mention notifications
    mentions = activity.mentions_json or []
    if mentions:
        try:
            from app.domains.notification.service import send_notification
            creator = user.get("real_name") or user.get("username", "")
            for m in mentions:
                uid = m.get("user_id") if isinstance(m, dict) else None
                if uid and uid != user["sub"]:
                    await send_notification(
                        db=db, tenant_id=tenant_id, recipient_id=uid,
                        type="mention",
                        title=f"{creator} 在活动中@了你",
                        content=f"{creator} 在「{activity.subject or '活动'}」中提及了你: {(activity.content or '')[:100]}",
                        biz_type=activity.biz_type, biz_id=activity.biz_id,
                    )
        except Exception:
            pass  # Non-critical

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
    biz_type, biz_id = activity.biz_type, activity.biz_id
    await db.delete(activity)
    await db.commit()
    # 删除客户活动后同步冗余的「最新跟进」，删的可能正是最新一条
    if biz_type == "customer":
        try:
            await _sync_customer_last_activity(db, tenant_id, biz_id)
        except Exception:
            pass
