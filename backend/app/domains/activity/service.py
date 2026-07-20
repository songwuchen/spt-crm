from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.activity.models import Activity
from app.domains.activity.schemas import ActivityCreate, ActivityUpdate
from app.domains.audit.service import log_action


# ==================== 父对象可见性 ====================
#
# 跟进记录/附件这类「挂在业务对象上的从属记录」自身没有归属字段，可见性完全取决于父对象。
# 不校验父对象的话，知道一个客户 id 就能把它名下的全部跟进历史/附件读走——列表页看不到
# 那条客户也拦不住。下面两个助手是这条判定的唯一实现，attachment 域直接复用（函数内导入）。

async def _load_biz_object(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str):
    """把 (biz_type, biz_id) 解析成用于判权的业务对象。

    返回 (对象, 判定方式)：owner=自带归属字段，project_child=看所属商机的归属。
    未收录的 biz_type（知识文档/审批流/工作流实例等）返回 (None, None)，表示不在本次
    数据范围修复的范围内，按原样放行——它们各自的域自行决定可见性。
    """
    async def _first(model, ident):
        if not ident:
            return None
        return (await db.execute(
            select(model).where(model.id == ident, model.tenant_id == tenant_id)
        )).scalar_one_or_none()

    # 自带 owner_id 的顶层实体
    if biz_type == "customer":
        from app.domains.customer.models import Customer
        return await _first(Customer, biz_id), "owner"
    if biz_type == "lead":
        from app.domains.lead.models import Lead
        return await _first(Lead, biz_id), "owner"
    if biz_type == "project":
        from app.domains.project.models import OpportunityProject
        return await _first(OpportunityProject, biz_id), "owner"
    if biz_type == "order":
        from app.domains.order.models import Order
        return await _first(Order, biz_id), "owner"
    if biz_type == "tender":
        from app.domains.tender.models import Tender
        return await _first(Tender, biz_id), "owner"
    if biz_type == "service_ticket":
        # 工单有自己的一套可见性（指派人/报单人/未分配池/父客户/父商机），
        # 单独判定后直接返回结论，不走下面 owner/project_child 两种口径
        from app.domains.service_ticket.models import ServiceTicket
        return await _first(ServiceTicket, biz_id), "service_ticket"

    # 商机子实体：按所属商机判定
    if biz_type == "quote":
        from app.domains.quote.models import Quote
        return await _first(Quote, biz_id), "project_child"
    if biz_type == "contract":
        from app.domains.contract.models import Contract
        return await _first(Contract, biz_id), "project_child"
    if biz_type == "solution":
        from app.domains.solution.models import Solution
        return await _first(Solution, biz_id), "project_child"
    if biz_type == "change":
        from app.domains.change.models import ChangeRequest
        return await _first(ChangeRequest, biz_id), "project_child"
    if biz_type == "delivery_milestone":
        from app.domains.delivery.models import DeliveryMilestone
        return await _first(DeliveryMilestone, biz_id), "project_child"

    # 版本行自身无归属，回落到它的主实体
    if biz_type == "quote_version":
        from app.domains.quote.models import Quote, QuoteVersion
        v = await _first(QuoteVersion, biz_id)
        return (await _first(Quote, v.quote_id) if v else None), "project_child"
    if biz_type == "contract_version":
        from app.domains.contract.models import Contract, ContractVersion
        v = await _first(ContractVersion, biz_id)
        return (await _first(Contract, v.contract_id) if v else None), "project_child"
    if biz_type == "solution_version":
        from app.domains.solution.models import Solution, SolutionVersion
        v = await _first(SolutionVersion, biz_id)
        return (await _first(Solution, v.solution_id) if v else None), "project_child"

    return None, None


async def assert_biz_object_visible(
    db: AsyncSession, tenant_id: str, user: dict | None,
    biz_type: str | None, biz_id: str | None, label: str = "该业务对象",
) -> None:
    """父业务对象不在数据范围内即抛 403。user=None 为系统内部调用，跳过。

    开放平台的系统主体（SYSTEM_ROLE）同样按内部调用处理：它不属于任何部门，
    若按登录用户口径判定，外部集成写入的跟进记录/附件会被自己的数据范围拒掉。
    """
    if user is None or not biz_type or not biz_id:
        return
    from app.common.data_scope import (
        assert_in_scope, assert_project_child_in_scope, resolve_owner_scope,
    )
    from app.domains.lowcode.field_permission import is_system_principal
    if is_system_principal(user.get("roles")):
        return
    if await resolve_owner_scope(db, user, tenant_id) is None:
        return  # 管理员 / data_scope=all

    obj, kind = await _load_biz_object(db, tenant_id, biz_type, biz_id)
    if obj is None:
        return  # 未收录的 biz_type，或父对象已不存在（没有可泄露的内容）
    if kind == "service_ticket":
        from app.domains.service_ticket.service import get_ticket
        await get_ticket(db, tenant_id, obj.id, user)  # 越权即 403
    elif kind == "owner":
        await assert_in_scope(db, tenant_id, user, obj, biz_type, label=label)
    else:
        await assert_project_child_in_scope(db, tenant_id, user, obj, label=label)


async def visible_activity_clause(db: AsyncSession, tenant_id: str, user: dict):
    """全局跟进流的可见性条件；None 表示不限（管理员 / data_scope=all）。

    可见 = 本人写的 + 挂在本人看得见的业务对象上的。各业务对象的可见 id 直接用
    apply_data_scope 生成子查询，保证与各自列表页同口径（含创建人/ACL共享/项目成员）。
    """
    from app.common.data_scope import apply_data_scope, resolve_owner_scope, visible_customer_ids_select
    if await resolve_owner_scope(db, user, tenant_id) is None:
        return None

    uid = user.get("sub", "")
    conds = [Activity.created_by_id == uid]

    cust_ids = await visible_customer_ids_select(db, tenant_id, user)  # 含公海口径
    if cust_ids is not None:
        conds.append(and_(Activity.biz_type == "customer", Activity.biz_id.in_(cust_ids)))

    from app.domains.lead.models import Lead
    from app.domains.project.models import OpportunityProject
    from app.domains.order.models import Order
    for bt, model in (("lead", Lead), ("project", OpportunityProject), ("order", Order)):
        q = select(model.id).where(model.tenant_id == tenant_id)
        if hasattr(model, "is_deleted"):
            q = q.where(model.is_deleted == False)  # noqa: E712
        q = await apply_data_scope(q, db, tenant_id, user, model, bt)
        conds.append(and_(Activity.biz_type == bt, Activity.biz_id.in_(q)))

    return or_(*conds)


async def list_activities(
    db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str,
    limit: int = 50, offset: int = 0, user: dict | None = None,
):
    # 先确认父对象可见：此前只按 biz_type/biz_id 取，等于把任意客户的全部跟进历史开放给全员
    await assert_biz_object_visible(db, tenant_id, user, biz_type, biz_id, label="该业务对象的跟进记录")
    result = await db.execute(
        select(Activity).where(
            Activity.tenant_id == tenant_id,
            Activity.biz_type == biz_type,
            Activity.biz_id == biz_id,
        ).order_by(Activity.created_at.desc()).offset(offset).limit(limit)
    )
    return result.scalars().all()


async def get_activity(db: AsyncSession, tenant_id: str, activity_id: str, user: dict | None = None) -> Activity:
    """按 id 取跟进记录。传入 user 时按所挂业务对象校验可见性（本人写的始终可见）。"""
    a = (await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not a:
        raise BusinessException(code=NOT_FOUND, message="活动记录不存在")
    if user is not None and a.created_by_id != user.get("sub"):
        await assert_biz_object_visible(db, tenant_id, user, a.biz_type, a.biz_id, label="该跟进记录")
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
    # 写入侧同样要挡：否则能往看不见的客户名下塞跟进记录，还会顺带改写它的「最新跟进」冗余
    await assert_biz_object_visible(db, tenant_id, user, data.biz_type, data.biz_id, label="该业务对象")
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
    activity = await get_activity(db, tenant_id, activity_id, user)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(activity, field, val)
    await db.commit()
    await db.refresh(activity)
    return activity


async def delete_activity(db: AsyncSession, tenant_id: str, activity_id: str, user: dict | None = None):
    activity = await get_activity(db, tenant_id, activity_id, user)
    biz_type, biz_id = activity.biz_type, activity.biz_id
    await db.delete(activity)
    await db.commit()
    # 删除客户活动后同步冗余的「最新跟进」，删的可能正是最新一条
    if biz_type == "customer":
        try:
            await _sync_customer_last_activity(db, tenant_id, biz_id)
        except Exception:
            pass
