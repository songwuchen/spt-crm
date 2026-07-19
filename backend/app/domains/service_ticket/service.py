from datetime import datetime, timezone, timedelta

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
from app.common.code_generator import generate_code

# SLA targets per priority: (respond_hours, resolve_hours)
SLA_TARGETS = {
    "critical": (1, 4),
    "high": (2, 8),
    "medium": (4, 24),
    "low": (8, 72),
}



# ==================== ServiceTicket ====================

async def list_tickets(
    db: AsyncSession, tenant_id: str,
    customer_id: str | None = None, project_id: str | None = None,
    keyword: str | None = None, status: str | None = None,
    priority: str | None = None, ticket_type: str | None = None,
    page: int = 1, page_size: int = 20,
    current_user: dict | None = None,
    adv_filter: str | None = None, sort_by: str | None = None, sort_order: str | None = None,
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

    # 高级筛选（多字段/多条件，含自定义扩展字段）
    from app.common.search import (
        entity_search_context, filter_clause_from_schema_or_400, resolve_sort_from_schema,
    )
    search_schema = await entity_search_context("service_ticket", db, tenant_id)
    clause = filter_clause_from_schema_or_400(search_schema, adv_filter, {"user_id": (current_user or {}).get("sub")})
    if clause is not None:
        q = q.where(clause)
        count_q = count_q.where(clause)

    total = (await db.execute(count_q)).scalar() or 0
    order = resolve_sort_from_schema(search_schema, sort_by, sort_order, ServiceTicket.created_at.desc())
    result = await db.execute(
        q.order_by(order)
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
    now = datetime.now(timezone.utc)
    dump = data.model_dump(exclude_unset=True)
    # 字段级权限：丢弃用户对不可编辑/隐藏扩展字段的写入
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in dump:
        dump["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "service_ticket", dump["custom_fields_json"], None, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "service_ticket", dump["custom_fields_json"], user.get("roles"))
    # 原生字段策略：读取侧已按角色隐藏/脱敏，写入侧必须对称拦截
    dump = await enforce_native_field_policy(
        db, tenant_id, "service_ticket", dump, None, user.get("roles"))
    priority = dump.get("priority", "medium")
    respond_h, resolve_h = SLA_TARGETS.get(priority, SLA_TARGETS["medium"])
    ticket = ServiceTicket(
        id=generate_uuid(), tenant_id=tenant_id,
        ticket_no=await generate_code(db, tenant_id, "service_ticket"),
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        sla_respond_by=now + timedelta(hours=respond_h),
        sla_resolve_by=now + timedelta(hours=resolve_h),
        **dump,
    )
    db.add(ticket)
    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.service_ticket.created", "service_ticket", ticket.id, {
        "ticket_id": ticket.id, "ticket_no": ticket.ticket_no, "type": ticket.type,
        "priority": ticket.priority, "customer_id": ticket.customer_id,
    })
    await db.commit()
    await db.refresh(ticket)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="service_ticket", resource_id=ticket.id,
                     summary=f"创建售后工单: {ticket.ticket_no}")
    return ticket


async def submit_for_approval(db: AsyncSession, tenant_id: str, ticket_id: str, user: dict) -> ServiceTicket:
    """提交售后工单审批（内勤发起）。优先走新表单引擎工作流（若 service_ticket 已绑定并发布流程），
    否则回退到旧 approval 引擎策略。灰度按 biz_type 逐个切换。"""
    ticket = await get_ticket(db, tenant_id, ticket_id)
    title = f"售后工单审批: {ticket.ticket_no}"
    from app.domains.lowcode.workflow_service import start_for_biz
    pinst = await start_for_biz(db, tenant_id, "service_ticket", ticket.id, user, title=title)
    if pinst is None:
        from app.domains.approval.service import auto_trigger_approval
        await auto_trigger_approval(db, tenant_id, "service_ticket", ticket.id, title, user)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="submit", resource_type="service_ticket", resource_id=ticket.id,
                     summary=f"提交售后审批: {ticket.ticket_no}")
    return ticket


async def update_ticket(db: AsyncSession, tenant_id: str, ticket_id: str, data: ServiceTicketUpdate, user: dict) -> ServiceTicket:
    ticket = await get_ticket(db, tenant_id, ticket_id)
    old_assignee = ticket.assigned_to_id
    old_status = ticket.status
    _dump = data.model_dump(exclude_unset=True)
    # 字段级权限：不可编辑扩展字段保留原值，忽略用户改动
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in _dump:
        _dump["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "service_ticket", _dump["custom_fields_json"], ticket.custom_fields_json, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "service_ticket", _dump["custom_fields_json"], user.get("roles"))
    _dump = await enforce_native_field_policy(
        db, tenant_id, "service_ticket", _dump, ticket, user.get("roles"), required_scope="payload")
    for field, val in _dump.items():
        setattr(ticket, field, val)
    now = datetime.now(timezone.utc)
    # Auto-track SLA: first response when leaving "open"
    if old_status == "open" and ticket.status != "open" and not ticket.sla_responded_at:
        ticket.sla_responded_at = now
    # Auto-track SLA: resolution time when reaching "resolved"
    if ticket.status == "resolved" and old_status != "resolved" and not ticket.sla_resolved_at:
        ticket.sla_resolved_at = now
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
