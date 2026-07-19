from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.delivery.models import ErpOrderLink, DeliveryMilestone
from app.domains.delivery.schemas import (
    ErpOrderLinkCreate, ErpOrderLinkUpdate, MilestoneCreate, MilestoneUpdate,
)
from app.domains.audit.service import log_action


# ==================== ErpOrderLink ====================

async def list_order_links(db: AsyncSession, tenant_id: str, project_id: str, user: dict | None = None):
    q = select(ErpOrderLink).where(ErpOrderLink.tenant_id == tenant_id, ErpOrderLink.project_id == project_id)
    # 按 project_id 直接开列表时也要过滤：否则换个商机 id 就能读到别人商机的 ERP 关联
    if user is not None:
        from app.common.data_scope import apply_project_child_scope
        q, _ = await apply_project_child_scope(q, q, db, tenant_id, user, ErpOrderLink)
    result = await db.execute(q.order_by(ErpOrderLink.created_at.desc()))
    return result.scalars().all()


async def create_order_link(db: AsyncSession, tenant_id: str, project_id: str, data: ErpOrderLinkCreate, user: dict) -> ErpOrderLink:
    # 创建前校验父商机可见性：否则可以往看不到的商机下塞子记录（越权写入）
    from app.domains.project.service import get_project
    await get_project(db, tenant_id, project_id, user)
    link = ErpOrderLink(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id,
        **data.model_dump(exclude_unset=True),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="erp_order_link", resource_id=link.id,
                     summary=f"关联ERP订单: {data.erp_order_no}")
    return link


async def delete_order_link(db: AsyncSession, tenant_id: str, link_id: str, user: dict):
    link = (await db.execute(
        select(ErpOrderLink).where(ErpOrderLink.id == link_id, ErpOrderLink.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not link:
        raise BusinessException(code=NOT_FOUND, message="订单关联不存在")
    from app.common.data_scope import assert_project_child_in_scope
    await assert_project_child_in_scope(db, tenant_id, user, link, label="该订单关联")
    await db.delete(link)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="erp_order_link", resource_id=link_id,
                     summary=f"删除ERP订单关联: {link.erp_order_no}")


# ==================== DeliveryMilestone ====================

async def list_milestones(db: AsyncSession, tenant_id: str, project_id: str, user: dict | None = None):
    q = select(DeliveryMilestone).where(
        DeliveryMilestone.tenant_id == tenant_id, DeliveryMilestone.project_id == project_id,
    )
    # 按 project_id 直接开列表时也要过滤：否则换个商机 id 就能读到别人商机的交付计划
    if user is not None:
        from app.common.data_scope import apply_project_child_scope
        q, _ = await apply_project_child_scope(q, q, db, tenant_id, user, DeliveryMilestone)
    result = await db.execute(q.order_by(DeliveryMilestone.sort_order, DeliveryMilestone.created_at))
    return result.scalars().all()


async def get_milestone(db: AsyncSession, tenant_id: str, milestone_id: str, user: dict | None = None) -> DeliveryMilestone:
    """按 id 取里程碑。传入 user 时按所属商机校验数据范围（列表查不到的，按 id 也不该读到/改到）。

    user=None 表示系统内部调用（提醒 worker / ERP 同步等），不做范围校验。
    """
    ms = (await db.execute(
        select(DeliveryMilestone).where(DeliveryMilestone.id == milestone_id, DeliveryMilestone.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not ms:
        raise BusinessException(code=NOT_FOUND, message="里程碑不存在")
    from app.common.data_scope import assert_project_child_in_scope
    await assert_project_child_in_scope(db, tenant_id, user, ms, label="该里程碑")
    return ms


async def create_milestone(db: AsyncSession, tenant_id: str, project_id: str, data: MilestoneCreate, user: dict) -> DeliveryMilestone:
    # 创建前校验父商机可见性：否则可以往看不到的商机下塞子记录（越权写入）
    from app.domains.project.service import get_project
    await get_project(db, tenant_id, project_id, user)
    ms = DeliveryMilestone(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id,
        **data.model_dump(exclude_unset=True),
    )
    db.add(ms)
    await db.commit()
    await db.refresh(ms)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="delivery_milestone", resource_id=ms.id,
                     summary=f"创建交付里程碑: {data.milestone_code}")

    # 通知负责人：优先里程碑负责人(子模块负责人)，否则商机负责人；自己建给自己不通知(issue #62)
    try:
        from app.domains.project.models import OpportunityProject
        proj = (await db.execute(
            select(OpportunityProject).where(
                OpportunityProject.id == project_id, OpportunityProject.tenant_id == tenant_id)
        )).scalar_one_or_none()
        recipient_id = ms.assignee_id or (proj.owner_id if proj else None)
        if recipient_id and recipient_id != user["sub"]:
            actor = user.get("real_name") or user.get("username")
            proj_name = proj.name if proj else ""
            ms_name = ms.name or ms.milestone_code
            from app.common.auto_notify import notify_milestone_created
            await notify_milestone_created(db, tenant_id, proj_name, ms_name, recipient_id, actor, project_id)
            # 钉钉工作通知/待办（配置了企业应用且负责人有手机号时下发，否则安全跳过）
            try:
                from app.common.msg_integration import dispatch_todo
                await dispatch_todo(
                    db, tenant_id, recipient_id,
                    title=f"新交付里程碑：{ms_name}",
                    content=f"所属商机：{proj_name}\n创建人：{actor}\n请关注交付进度。",
                    link=f"/opportunities/{project_id}",
                )
            except Exception as e:
                import logging
                logging.getLogger("spt_crm.delivery").warning("DingTalk dispatch for milestone failed: %s", e)
    except Exception as e:
        import logging
        logging.getLogger("spt_crm.delivery").warning("Auto-notify milestone created failed: %s", e)
    return ms


async def update_milestone(db: AsyncSession, tenant_id: str, milestone_id: str, data: MilestoneUpdate, user: dict) -> DeliveryMilestone:
    ms = await get_milestone(db, tenant_id, milestone_id, user)
    old_status = ms.status
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(ms, field, val)
    await db.commit()
    await db.refresh(ms)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="delivery_milestone", resource_id=milestone_id,
                     summary=f"更新交付里程碑: {ms.milestone_code}")

    # 状态变更时通知负责人：优先里程碑负责人，否则商机负责人；自己改给自己不通知(issue #76)
    if ms.status != old_status:
        try:
            from app.domains.project.models import OpportunityProject
            proj = (await db.execute(
                select(OpportunityProject).where(
                    OpportunityProject.id == ms.project_id, OpportunityProject.tenant_id == tenant_id)
            )).scalar_one_or_none()
            recipient_id = ms.assignee_id or (proj.owner_id if proj else None)
            if recipient_id and recipient_id != user["sub"]:
                actor = user.get("real_name") or user.get("username")
                proj_name = proj.name if proj else ""
                ms_name = ms.name or ms.milestone_code
                from app.common.auto_notify import notify_milestone_status_changed
                await notify_milestone_status_changed(
                    db, tenant_id, proj_name, ms_name, old_status, ms.status,
                    recipient_id, actor, ms.project_id)
        except Exception as e:
            import logging
            logging.getLogger("spt_crm.delivery").warning("Auto-notify milestone status changed failed: %s", e)
    return ms


async def delete_milestone(db: AsyncSession, tenant_id: str, milestone_id: str, user: dict):
    ms = await get_milestone(db, tenant_id, milestone_id, user)
    await db.delete(ms)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="delivery_milestone", resource_id=milestone_id,
                     summary=f"删除交付里程碑: {ms.milestone_code}")
