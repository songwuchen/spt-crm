from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.service_ticket.models import ServiceTicket, RenewalOpportunity
from app.domains.service_ticket.schemas import (
    ServiceTicketCreate, ServiceTicketUpdate, RenewalCreate, RenewalUpdate,
)
from app.domains.audit.service import log_action


def _generate_ticket_no() -> str:
    now = datetime.now(timezone.utc)
    import random
    seq = random.randint(1000, 9999)
    return f"SRV-{now.strftime('%Y%m%d')}-{seq}"


# ==================== ServiceTicket ====================

async def list_tickets(
    db: AsyncSession, tenant_id: str,
    customer_id: str | None = None, project_id: str | None = None,
    keyword: str | None = None, status: str | None = None,
    priority: str | None = None, ticket_type: str | None = None,
    page: int = 1, page_size: int = 20,
):
    q = select(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id)
    count_q = select(func.count(ServiceTicket.id)).where(ServiceTicket.tenant_id == tenant_id)
    if customer_id:
        q = q.where(ServiceTicket.customer_id == customer_id)
        count_q = count_q.where(ServiceTicket.customer_id == customer_id)
    if project_id:
        q = q.where(ServiceTicket.project_id == project_id)
        count_q = count_q.where(ServiceTicket.project_id == project_id)
    if keyword:
        kw = f"%{keyword}%"
        from sqlalchemy import or_
        cond = or_(ServiceTicket.ticket_no.ilike(kw), ServiceTicket.description.ilike(kw))
        q = q.where(cond)
        count_q = count_q.where(cond)
    if status:
        q = q.where(ServiceTicket.status == status)
        count_q = count_q.where(ServiceTicket.status == status)
    if priority:
        q = q.where(ServiceTicket.priority == priority)
        count_q = count_q.where(ServiceTicket.priority == priority)
    if ticket_type:
        q = q.where(ServiceTicket.type == ticket_type)
        count_q = count_q.where(ServiceTicket.type == ticket_type)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        q.order_by(ServiceTicket.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    return result.scalars().all(), total


async def get_ticket(db: AsyncSession, tenant_id: str, ticket_id: str) -> ServiceTicket:
    t = (await db.execute(
        select(ServiceTicket).where(ServiceTicket.id == ticket_id, ServiceTicket.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not t:
        raise BusinessException(code=NOT_FOUND, message="工单不存在")
    return t


async def create_ticket(db: AsyncSession, tenant_id: str, data: ServiceTicketCreate, user: dict) -> ServiceTicket:
    ticket = ServiceTicket(
        id=generate_uuid(), tenant_id=tenant_id,
        ticket_no=_generate_ticket_no(),
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="service_ticket", resource_id=ticket.id,
                     summary=f"创建售后工单: {ticket.ticket_no}")
    return ticket


async def update_ticket(db: AsyncSession, tenant_id: str, ticket_id: str, data: ServiceTicketUpdate, user: dict) -> ServiceTicket:
    ticket = await get_ticket(db, tenant_id, ticket_id)
    old_assignee = ticket.assigned_to_id
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(ticket, field, val)
    await db.commit()
    await db.refresh(ticket)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="service_ticket", resource_id=ticket_id,
                     summary=f"更新售后工单: {ticket.ticket_no} → {ticket.status}")

    # Auto-activity: record status change on ticket timeline
    try:
        from app.common.auto_activity import record_activity
        status_labels = {"open": "待处理", "assigned": "已分配", "in_progress": "处理中", "resolved": "已解决", "closed": "已关闭"}
        await record_activity(db, tenant_id, "service_ticket", ticket_id, "system",
                              f"工单状态更新: {status_labels.get(ticket.status, ticket.status)}", None,
                              user["sub"], user.get("real_name") or user.get("username"))
    except Exception:
        pass

    # Auto-notify new assignee
    try:
        new_assignee = ticket.assigned_to_id
        if new_assignee and new_assignee != old_assignee and new_assignee != user["sub"]:
            from app.common.auto_notify import notify_ticket_assigned
            await notify_ticket_assigned(db, tenant_id, ticket.ticket_no, new_assignee,
                                          user.get("real_name") or user.get("username"), ticket_id)
    except Exception:
        pass

    return ticket


async def delete_ticket(db: AsyncSession, tenant_id: str, ticket_id: str, user: dict):
    ticket = await get_ticket(db, tenant_id, ticket_id)
    await db.delete(ticket)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="service_ticket", resource_id=ticket_id,
                     summary=f"删除售后工单: {ticket.ticket_no}")


# ==================== RenewalOpportunity ====================

async def list_renewals(db: AsyncSession, tenant_id: str, customer_id: str | None = None, status: str | None = None):
    q = select(RenewalOpportunity).where(RenewalOpportunity.tenant_id == tenant_id)
    if customer_id:
        q = q.where(RenewalOpportunity.customer_id == customer_id)
    if status:
        q = q.where(RenewalOpportunity.status == status)
    result = await db.execute(q.order_by(RenewalOpportunity.created_at.desc()))
    return result.scalars().all()


async def get_renewal(db: AsyncSession, tenant_id: str, renewal_id: str) -> RenewalOpportunity:
    r = (await db.execute(
        select(RenewalOpportunity).where(RenewalOpportunity.id == renewal_id, RenewalOpportunity.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not r:
        raise BusinessException(code=NOT_FOUND, message="复购机会不存在")
    return r


async def create_renewal(db: AsyncSession, tenant_id: str, data: RenewalCreate, user: dict) -> RenewalOpportunity:
    dump = data.model_dump(exclude_unset=True)
    if "owner_id" not in dump:
        dump["owner_id"] = user["sub"]
    if "owner_name" not in dump:
        dump["owner_name"] = user.get("real_name") or user.get("username")
    renewal = RenewalOpportunity(
        id=generate_uuid(), tenant_id=tenant_id,
        **dump,
    )
    db.add(renewal)
    await db.commit()
    await db.refresh(renewal)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="renewal_opportunity", resource_id=renewal.id,
                     summary=f"创建复购机会: {data.name}")
    return renewal


async def update_renewal(db: AsyncSession, tenant_id: str, renewal_id: str, data: RenewalUpdate, user: dict) -> RenewalOpportunity:
    renewal = await get_renewal(db, tenant_id, renewal_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(renewal, field, val)
    await db.commit()
    await db.refresh(renewal)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="renewal_opportunity", resource_id=renewal_id,
                     summary=f"更新复购机会: {renewal.name}")
    return renewal
