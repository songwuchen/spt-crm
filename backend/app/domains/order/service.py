import logging

from sqlalchemy import select, func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.common.code_generator import generate_code
from app.domains.order.models import Order, OrderLine
from app.domains.order.schemas import OrderCreate, OrderUpdate, OrderShip
from app.domains.audit.service import log_action

logger = logging.getLogger("spt_crm.order")


def _round2(v: float) -> float:
    return round(float(v or 0), 2)


async def list_lines(db: AsyncSession, tenant_id: str, order_id: str):
    return (await db.execute(
        select(OrderLine).where(OrderLine.tenant_id == tenant_id, OrderLine.order_id == order_id)
        .order_by(OrderLine.sort_order, OrderLine.created_at)
    )).scalars().all()


async def _replace_lines(db: AsyncSession, tenant_id: str, order_id: str, lines) -> float:
    """用给定明细整体替换订单明细，返回合计金额。lines 为 OrderLineIn 列表。"""
    await db.execute(sql_delete(OrderLine).where(
        OrderLine.tenant_id == tenant_id, OrderLine.order_id == order_id))
    total = 0.0
    for i, ln in enumerate(lines):
        amount = _round2(ln.quantity * ln.unit_price)
        total += amount
        db.add(OrderLine(
            id=generate_uuid(), tenant_id=tenant_id, order_id=order_id,
            product_id=ln.product_id, product_name=ln.product_name,
            spec=ln.spec, unit=ln.unit,
            quantity=ln.quantity, unit_price=ln.unit_price, amount=amount,
            shipped_quantity=0, sort_order=i,
        ))
    return _round2(total)


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
    lines = payload.pop("lines", None)
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
    await db.flush()  # 先拿到 order.id 再存明细
    # 有明细时：整体保存明细，并用明细汇总覆盖合计金额
    if data.lines is not None:
        total = await _replace_lines(db, tenant_id, order.id, data.lines)
        order.amount = total
    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.order.created", "order", order.id, {
        "order_id": order.id, "order_no": order.order_no, "customer_id": order.customer_id,
        "amount": float(order.amount) if order.amount else None, "status": order.status,
    })
    await db.commit()
    await db.refresh(order)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="order", resource_id=order.id,
                     summary=f"创建订单: {order.order_no}")

    # 生成待办，推送给负责人（自己给自己建单不通知）
    if order.owner_id and order.owner_id != user["sub"]:
        actor = user.get("real_name") or user.get("username")
        try:
            from app.common.auto_notify import notify_order_assigned
            await notify_order_assigned(db, tenant_id, order.order_no, order.owner_id, actor, order.id)
        except Exception:
            pass
        # 钉钉待办/工作通知（已配置企业应用且负责人有手机号时下发）
        try:
            from app.common.msg_integration import dispatch_todo
            await dispatch_todo(
                db, tenant_id, order.owner_id,
                title=f"新订单待处理：{order.order_no}",
                content=f"{order.title or order.order_no}\n创建人：{actor}\n请及时跟进订单处理。",
                link="/orders",
            )
        except Exception as e:
            logger.warning("DingTalk todo dispatch for order failed: %s", e)
    return order


async def update_order(db: AsyncSession, tenant_id: str, order_id: str, data: OrderUpdate, user: dict) -> Order:
    order = await get_order(db, tenant_id, order_id)
    dump = data.model_dump(exclude_unset=True)
    lines_given = "lines" in dump
    dump.pop("lines", None)  # 明细单独处理，不能 setattr 到模型
    old_status = order.status
    for field, val in dump.items():
        setattr(order, field, val)
    if lines_given:
        total = await _replace_lines(db, tenant_id, order_id, data.lines or [])
        order.amount = total
    if "status" in dump and order.status != old_status:
        from app.domains.outbox.service import emit_event
        await emit_event(db, tenant_id, "crm.order.status_changed", "order", order.id, {
            "order_id": order.id, "order_no": order.order_no,
            "from_status": old_status, "to_status": order.status,
        })
    await db.commit()
    await db.refresh(order)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="order", resource_id=order.id,
                     summary=f"更新订单: {order.order_no}")
    return order


async def submit_for_approval(db: AsyncSession, tenant_id: str, order_id: str, user: dict) -> Order:
    """提交订单审批（内勤发起）。按已配置的 order 审批策略自动建立审批流。"""
    order = await get_order(db, tenant_id, order_id)
    from app.domains.approval.service import auto_trigger_approval
    await auto_trigger_approval(db, tenant_id, "order", order.id, f"订单审批: {order.order_no}", user)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="submit", resource_type="order", resource_id=order.id,
                     summary=f"提交订单审批: {order.order_no}")
    return order


def ship_status(lines) -> str:
    """根据明细已发货数量推导发货状态：none / partial / full。"""
    if not lines:
        return "none"
    total = sum(float(l.quantity or 0) for l in lines)
    shipped = sum(float(l.shipped_quantity or 0) for l in lines)
    if shipped <= 0:
        return "none"
    if shipped >= total:
        return "full"
    return "partial"


async def ship_order(db: AsyncSession, tenant_id: str, order_id: str, data: OrderShip, user: dict) -> Order:
    """发货：支持部分发货（按行登记本次发货数量）或一键全部发货。"""
    order = await get_order(db, tenant_id, order_id)
    lines = await list_lines(db, tenant_id, order_id)
    if not lines:
        raise BusinessException(code=BUSINESS_ERROR, message="订单无明细，无法发货")
    if data.full:
        for ln in lines:
            ln.shipped_quantity = ln.quantity
    else:
        add_map = {it.line_id: float(it.ship_quantity) for it in (data.items or [])}
        if not add_map:
            raise BusinessException(code=BUSINESS_ERROR, message="请填写本次发货数量，或选择全部发货")
        for ln in lines:
            if ln.id in add_map:
                newq = float(ln.shipped_quantity or 0) + add_map[ln.id]
                # 不允许超过订单数量
                ln.shipped_quantity = min(newq, float(ln.quantity or 0))
    st = ship_status(lines)
    if st == "full":
        order.status = "shipped"
    elif st == "partial" and order.status in ("draft", "confirmed", "producing"):
        order.status = "producing"
    await db.commit()
    await db.refresh(order)

    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.order.shipped", "order", order.id, {
        "order_id": order.id, "order_no": order.order_no, "ship_status": st,
    })
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="ship", resource_type="order", resource_id=order.id,
                     summary=f"订单发货（{ {'full': '全部', 'partial': '部分'}.get(st, st) }）: {order.order_no}")
    return order


async def delete_order(db: AsyncSession, tenant_id: str, order_id: str, user: dict):
    order = await get_order(db, tenant_id, order_id)
    order.is_deleted = True
    await db.execute(sql_delete(OrderLine).where(
        OrderLine.tenant_id == tenant_id, OrderLine.order_id == order_id))
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="order", resource_id=order_id,
                     summary=f"删除订单: {order.order_no}")
