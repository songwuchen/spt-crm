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

async def list_order_links(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(ErpOrderLink).where(ErpOrderLink.tenant_id == tenant_id, ErpOrderLink.project_id == project_id)
        .order_by(ErpOrderLink.created_at.desc())
    )
    return result.scalars().all()


async def create_order_link(db: AsyncSession, tenant_id: str, project_id: str, data: ErpOrderLinkCreate, user: dict) -> ErpOrderLink:
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
    await db.delete(link)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="erp_order_link", resource_id=link_id,
                     summary=f"删除ERP订单关联: {link.erp_order_no}")


# ==================== DeliveryMilestone ====================

async def list_milestones(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(DeliveryMilestone).where(
            DeliveryMilestone.tenant_id == tenant_id, DeliveryMilestone.project_id == project_id,
        ).order_by(DeliveryMilestone.sort_order, DeliveryMilestone.created_at)
    )
    return result.scalars().all()


async def get_milestone(db: AsyncSession, tenant_id: str, milestone_id: str) -> DeliveryMilestone:
    ms = (await db.execute(
        select(DeliveryMilestone).where(DeliveryMilestone.id == milestone_id, DeliveryMilestone.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not ms:
        raise BusinessException(code=NOT_FOUND, message="里程碑不存在")
    return ms


async def create_milestone(db: AsyncSession, tenant_id: str, project_id: str, data: MilestoneCreate, user: dict) -> DeliveryMilestone:
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
    return ms


async def update_milestone(db: AsyncSession, tenant_id: str, milestone_id: str, data: MilestoneUpdate, user: dict) -> DeliveryMilestone:
    ms = (await db.execute(
        select(DeliveryMilestone).where(DeliveryMilestone.id == milestone_id, DeliveryMilestone.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not ms:
        raise BusinessException(code=NOT_FOUND, message="里程碑不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(ms, field, val)
    await db.commit()
    await db.refresh(ms)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="delivery_milestone", resource_id=milestone_id,
                     summary=f"更新交付里程碑: {ms.milestone_code}")
    return ms


async def delete_milestone(db: AsyncSession, tenant_id: str, milestone_id: str, user: dict):
    ms = (await db.execute(
        select(DeliveryMilestone).where(DeliveryMilestone.id == milestone_id, DeliveryMilestone.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not ms:
        raise BusinessException(code=NOT_FOUND, message="里程碑不存在")
    await db.delete(ms)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="delivery_milestone", resource_id=milestone_id,
                     summary=f"删除交付里程碑: {ms.milestone_code}")
