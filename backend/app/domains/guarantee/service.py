"""保函/保证金台账 service。"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.common.code_generator import generate_code
from app.domains.audit.service import log_action
from app.domains.guarantee.models import Guarantee
from app.domains.guarantee.schemas import GuaranteeCreate, GuaranteeUpdate, GuaranteeReturn

logger = logging.getLogger("spt_crm.guarantee")


async def mark_expired(db: AsyncSession, tenant_id: str):
    """Auto-mark active guarantees past expiry as expired."""
    await db.execute(
        update(Guarantee).where(
            Guarantee.tenant_id == tenant_id,
            Guarantee.status == "active",
            Guarantee.expiry_date < date.today(),
        ).values(status="expired")
    )
    await db.commit()


async def list_guarantees(db, tenant_id, page_no=1, page_size=20, type=None, status=None, keyword=None):
    await mark_expired(db, tenant_id)
    base = select(Guarantee).where(Guarantee.tenant_id == tenant_id)
    if type:
        base = base.where(Guarantee.type == type)
    if status:
        base = base.where(Guarantee.status == status)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(
            Guarantee.guarantee_no.ilike(kw) | Guarantee.customer_name.ilike(kw) | Guarantee.issuer.ilike(kw)
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(Guarantee.expiry_date.asc().nullslast(), Guarantee.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_guarantee(db, tenant_id, gid) -> Guarantee:
    g = (await db.execute(
        select(Guarantee).where(Guarantee.id == gid, Guarantee.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not g:
        raise BusinessException(code=NOT_FOUND, message="保函不存在")
    return g


async def create_guarantee(db, tenant_id, data: GuaranteeCreate, user: dict) -> Guarantee:
    dump = data.model_dump(exclude_unset=True)
    if not dump.get("guarantee_no"):
        dump["guarantee_no"] = await generate_code(db, tenant_id, "guarantee")
    g = Guarantee(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **dump,
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="guarantee", resource_id=g.id,
                     summary=f"登记保函: {g.guarantee_no}")
    return g


async def update_guarantee(db, tenant_id, gid, data: GuaranteeUpdate, user: dict) -> Guarantee:
    g = await get_guarantee(db, tenant_id, gid)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(g, field, val)
    await db.commit()
    await db.refresh(g)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="guarantee", resource_id=g.id,
                     summary=f"更新保函: {g.guarantee_no}")
    return g


async def mark_returned(db, tenant_id, gid, data: GuaranteeReturn, user: dict) -> Guarantee:
    g = await get_guarantee(db, tenant_id, gid)
    g.status = "returned"
    g.return_date = data.return_date or date.today()
    if data.remark is not None:
        g.remark = data.remark
    await db.commit()
    await db.refresh(g)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="guarantee", resource_id=g.id,
                     summary=f"保函退还: {g.guarantee_no}")
    return g


async def delete_guarantee(db, tenant_id, gid, user: dict):
    g = await get_guarantee(db, tenant_id, gid)
    await db.delete(g)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="guarantee", resource_id=gid,
                     summary=f"删除保函: {g.guarantee_no}")


async def summary(db, tenant_id):
    await mark_expired(db, tenant_id)
    rows = (await db.execute(
        select(Guarantee.status, func.count(Guarantee.id), func.coalesce(func.sum(Guarantee.amount), 0))
        .where(Guarantee.tenant_id == tenant_id).group_by(Guarantee.status)
    )).all()
    by_status = {s: {"count": c, "amount": float(a)} for s, c, a in rows}
    # active amount + expiring within 30 days
    soon = date.today() + timedelta(days=30)
    expiring_cnt = (await db.execute(
        select(func.count(Guarantee.id)).where(
            Guarantee.tenant_id == tenant_id, Guarantee.status == "active",
            Guarantee.expiry_date != None, Guarantee.expiry_date <= soon)  # noqa: E711
    )).scalar() or 0
    active_amount = float((by_status.get("active") or {}).get("amount", 0))
    return {"by_status": by_status, "active_amount": active_amount, "expiring_30d": expiring_cnt}


async def list_expiring(db, tenant_id, days=30):
    await mark_expired(db, tenant_id)
    soon = date.today() + timedelta(days=days)
    items = (await db.execute(
        select(Guarantee).where(
            Guarantee.tenant_id == tenant_id, Guarantee.status == "active",
            Guarantee.expiry_date != None, Guarantee.expiry_date <= soon)  # noqa: E711
        .order_by(Guarantee.expiry_date.asc())
    )).scalars().all()
    return items


async def check_expiring_and_notify(db, tenant_id, days=30) -> int:
    """Notify owners of guarantees expiring within `days`."""
    from app.domains.notification.service import send_notification
    items = await list_expiring(db, tenant_id, days)
    notified = 0
    for g in items:
        if not g.owner_id:
            continue
        try:
            await send_notification(
                db, tenant_id, recipient_id=g.owner_id, type="guarantee_expiring",
                title=f"保函即将到期: {g.guarantee_no}",
                content=f"保函「{g.guarantee_no}」({g.customer_name or ''}) 将于 {g.expiry_date} 到期，金额 ¥{float(g.amount or 0):,.2f}，请及时办理退还/续期。",
                biz_type="guarantee", biz_id=g.id, sender_name="系统",
            )
            notified += 1
        except Exception as e:
            logger.warning("guarantee expiring notify failed: %s", e)
    return notified
