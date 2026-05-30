from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.common.code_generator import generate_code
from app.domains.order.models import Order
from app.domains.order.schemas import OrderCreate, OrderUpdate
from app.domains.audit.service import log_action


async def list_orders(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    customer_id: str | None = None, status: str | None = None, keyword: str | None = None,
):
    base = select(Order).where(Order.tenant_id == tenant_id, Order.is_deleted == False)
    if customer_id:
        base = base.where(Order.customer_id == customer_id)
    if status:
        base = base.where(Order.status == status)
    if keyword:
        base = base.where(Order.order_no.ilike(f"%{keyword}%") | Order.title.ilike(f"%{keyword}%"))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(Order.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_order(db: AsyncSession, tenant_id: str, order_id: str) -> Order:
    o = (await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id, Order.is_deleted == False)
    )).scalar_one_or_none()
    if not o:
        raise BusinessException(code=NOT_FOUND, message="订单不存在")
    return o


async def create_order(db: AsyncSession, tenant_id: str, data: OrderCreate, user: dict) -> Order:
    payload = data.model_dump()
    chosen_owner_id = payload.pop("owner_id", None)
    if chosen_owner_id:
        from app.domains.auth.models import User as AuthUser
        owner = (await db.execute(
            select(AuthUser).where(AuthUser.id == chosen_owner_id, AuthUser.tenant_id == tenant_id)
        )).scalar_one_or_none()
        owner_id = chosen_owner_id
        owner_name = (owner.real_name or owner.username) if owner else None
    else:
        owner_id = user["sub"]
        owner_name = user.get("real_name") or user.get("username")

    order = Order(
        id=generate_uuid(), tenant_id=tenant_id,
        order_no=await generate_code(db, tenant_id, "order"),
        owner_id=owner_id, owner_name=owner_name,
        **payload,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="order", resource_id=order.id,
                     summary=f"创建订单: {order.order_no}")
    return order


async def update_order(db: AsyncSession, tenant_id: str, order_id: str, data: OrderUpdate, user: dict) -> Order:
    order = await get_order(db, tenant_id, order_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(order, field, val)
    await db.commit()
    await db.refresh(order)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="order", resource_id=order.id,
                     summary=f"更新订单: {order.order_no}")
    return order


async def delete_order(db: AsyncSession, tenant_id: str, order_id: str, user: dict):
    order = await get_order(db, tenant_id, order_id)
    order.is_deleted = True
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="order", resource_id=order_id,
                     summary=f"删除订单: {order.order_no}")
