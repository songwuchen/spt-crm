"""客户工艺与设备档案 service。"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.audit.service import log_action
from app.domains.equipment.models import CustomerEquipment, CustomerProcessSurvey
from app.domains.equipment.schemas import (
    EquipmentCreate, EquipmentUpdate, EquipmentToRenewal, SurveyCreate, SurveyUpdate,
)

logger = logging.getLogger("spt_crm.equipment")


# ==================== Equipment ====================
async def list_equipment(db, tenant_id, page_no=1, page_size=20, customer_id=None,
                         is_competitor=None, keyword=None):
    base = select(CustomerEquipment).where(CustomerEquipment.tenant_id == tenant_id)
    if customer_id:
        base = base.where(CustomerEquipment.customer_id == customer_id)
    if is_competitor is not None:
        base = base.where(CustomerEquipment.is_competitor == is_competitor)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(
            CustomerEquipment.name.ilike(kw) | CustomerEquipment.customer_name.ilike(kw)
            | CustomerEquipment.supplier.ilike(kw) | CustomerEquipment.spec.ilike(kw)
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(CustomerEquipment.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_equipment(db, tenant_id, eid) -> CustomerEquipment:
    e = (await db.execute(
        select(CustomerEquipment).where(CustomerEquipment.id == eid, CustomerEquipment.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not e:
        raise BusinessException(code=NOT_FOUND, message="设备记录不存在")
    return e


async def create_equipment(db, tenant_id, data: EquipmentCreate, user: dict) -> CustomerEquipment:
    e = CustomerEquipment(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="equipment", resource_id=e.id,
                     summary=f"登记客户设备: {e.name}")
    return e


async def update_equipment(db, tenant_id, eid, data: EquipmentUpdate, user: dict) -> CustomerEquipment:
    e = await get_equipment(db, tenant_id, eid)
    for f, v in data.model_dump(exclude_unset=True).items():
        setattr(e, f, v)
    await db.commit()
    await db.refresh(e)
    return e


async def delete_equipment(db, tenant_id, eid, user: dict):
    e = await get_equipment(db, tenant_id, eid)
    await db.delete(e)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="equipment", resource_id=eid,
                     summary=f"删除客户设备: {e.name}")


async def replacement_candidates(db, tenant_id, months=12):
    """竞品设备且计划更换在 months 个月内（或使用年限较长）。"""
    cutoff = date.today() + timedelta(days=months * 30)
    rows = (await db.execute(
        select(CustomerEquipment).where(
            CustomerEquipment.tenant_id == tenant_id,
            CustomerEquipment.is_competitor == True,  # noqa: E712
            CustomerEquipment.replace_plan_date != None,  # noqa: E711
            CustomerEquipment.replace_plan_date <= cutoff,
        ).order_by(CustomerEquipment.replace_plan_date.asc())
    )).scalars().all()
    return rows


async def convert_to_renewal(db, tenant_id, eid, data: EquipmentToRenewal, user: dict):
    """从竞品设备生成"替换/复购商机"（RenewalOpportunity）。"""
    from app.domains.service_ticket.models import RenewalOpportunity
    e = await get_equipment(db, tenant_id, eid)
    name = data.name or f"{e.customer_name or ''} {e.name} 替换商机".strip()
    r = RenewalOpportunity(
        id=generate_uuid(), tenant_id=tenant_id,
        customer_id=e.customer_id, name=name[:200],
        amount_expect=data.amount_expect, close_date_expect=data.close_date_expect,
        related_asset_json={"equipment_id": e.id, "equipment_name": e.name, "supplier": e.supplier},
        status="open", owner_id=user["sub"], owner_name=user.get("real_name") or user.get("username"),
        remark=data.remark or f"由竞品设备「{e.name}（{e.supplier or '未知厂家'}）」转化",
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="renewal", resource_id=r.id,
                     summary=f"竞品替换商机: {name}")
    return r


# ==================== Process Survey ====================
async def list_surveys(db, tenant_id, page_no=1, page_size=20, customer_id=None, industry=None, keyword=None):
    base = select(CustomerProcessSurvey).where(CustomerProcessSurvey.tenant_id == tenant_id)
    if customer_id:
        base = base.where(CustomerProcessSurvey.customer_id == customer_id)
    if industry:
        base = base.where(CustomerProcessSurvey.industry == industry)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(
            CustomerProcessSurvey.customer_name.ilike(kw) | CustomerProcessSurvey.main_products.ilike(kw)
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(CustomerProcessSurvey.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_survey(db, tenant_id, sid) -> CustomerProcessSurvey:
    s = (await db.execute(
        select(CustomerProcessSurvey).where(CustomerProcessSurvey.id == sid, CustomerProcessSurvey.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not s:
        raise BusinessException(code=NOT_FOUND, message="工艺调研不存在")
    return s


async def create_survey(db, tenant_id, data: SurveyCreate, user: dict) -> CustomerProcessSurvey:
    s = CustomerProcessSurvey(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def update_survey(db, tenant_id, sid, data: SurveyUpdate, user: dict) -> CustomerProcessSurvey:
    s = await get_survey(db, tenant_id, sid)
    for f, v in data.model_dump(exclude_unset=True).items():
        setattr(s, f, v)
    await db.commit()
    await db.refresh(s)
    return s


async def delete_survey(db, tenant_id, sid, user: dict):
    s = await get_survey(db, tenant_id, sid)
    await db.delete(s)
    await db.commit()
