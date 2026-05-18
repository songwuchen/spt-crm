import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, LEAD_ALREADY_QUALIFIED, LEAD_ALREADY_DISCARDED
from app.common.code_generator import generate_code
from app.domains.lead.models import Lead
from app.domains.lead.schemas import LeadCreate, LeadUpdate
from app.domains.customer.models import Customer
from app.domains.audit.service import log_action

logger = logging.getLogger("spt_crm.lead")



def _derived_region(lead: Lead) -> str | None:
    """Concat province/city/district into a single display string."""
    parts = [p for p in (lead.province, lead.city, lead.district) if p]
    return "".join(parts) if parts else None


def _compute_score(lead: Lead) -> int:
    """Basic rule-based scoring per requirements: source, industry, demand, budget, contact."""
    score = 0
    if lead.company_name:
        score += 15
    if lead.contact_phone or lead.contact_email:
        score += 15
    if lead.contact_name:
        score += 10
    if lead.industry:
        score += 10
    if lead.region:
        score += 5
    if lead.source:
        score += 10
    if lead.demand_summary:
        score += 15
    if lead.budget_range:
        score += 10
    # Extra: multiple contact methods
    if lead.contact_phone and lead.contact_email:
        score += 10
    return min(score, 100)


async def list_leads(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, status: str | None = None, owner_id: str | None = None,
    customer_type: str | None = None, category: str | None = None,
    country_type: str | None = None, province: str | None = None,
    department_id: str | None = None, industry: str | None = None,
):
    base = select(Lead).where(Lead.tenant_id == tenant_id, Lead.is_deleted == False)
    if keyword:
        base = base.where(Lead.title.ilike(f"%{keyword}%") | Lead.company_name.ilike(f"%{keyword}%") | Lead.lead_code.ilike(f"%{keyword}%"))
    if status:
        base = base.where(Lead.status == status)
    if owner_id:
        base = base.where(Lead.owner_id == owner_id)
    if customer_type:
        base = base.where(Lead.customer_type == customer_type)
    if category:
        base = base.where(Lead.category == category)
    if country_type:
        base = base.where(Lead.country_type == country_type)
    if province:
        base = base.where(Lead.province == province)
    if department_id:
        base = base.where(Lead.department_id == department_id)
    if industry:
        base = base.where(Lead.industry == industry)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(Lead.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_lead(db: AsyncSession, tenant_id: str, lead_id: str) -> Lead:
    lead = (await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id, Lead.is_deleted == False)
    )).scalar_one_or_none()
    if not lead:
        raise BusinessException(code=NOT_FOUND, message="线索不存在")
    return lead


async def create_lead(db: AsyncSession, tenant_id: str, data: LeadCreate, user: dict) -> Lead:
    payload = data.model_dump()
    # If user picked an owner in the form, look up that user's name; otherwise fall back to creator.
    chosen_owner_id = payload.pop("owner_id", None)
    if chosen_owner_id:
        from app.domains.auth.models import User as AuthUser
        owner = (await db.execute(select(AuthUser).where(AuthUser.id == chosen_owner_id))).scalar_one_or_none()
        owner_id = chosen_owner_id
        owner_name = (owner.real_name or owner.username) if owner else None
    else:
        owner_id = user["sub"]
        owner_name = user.get("real_name") or user.get("username")

    lead = Lead(
        id=generate_uuid(), tenant_id=tenant_id,
        lead_code=await generate_code(db, tenant_id, "lead"),
        owner_id=owner_id, owner_name=owner_name,
        **payload,
    )
    lead.score = _compute_score(lead)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="lead", resource_id=lead.id,
                     summary=f"创建线索: {lead.title}")
    return lead


async def update_lead(db: AsyncSession, tenant_id: str, lead_id: str, data: LeadUpdate, user: dict) -> Lead:
    lead = await get_lead(db, tenant_id, lead_id)
    payload = data.model_dump(exclude_unset=True)
    # When owner changes, refresh owner_name to match
    if "owner_id" in payload and payload["owner_id"] and payload["owner_id"] != lead.owner_id:
        from app.domains.auth.models import User as AuthUser
        new_owner = (await db.execute(select(AuthUser).where(AuthUser.id == payload["owner_id"]))).scalar_one_or_none()
        if new_owner:
            lead.owner_name = new_owner.real_name or new_owner.username
    for field, val in payload.items():
        setattr(lead, field, val)
    lead.score = _compute_score(lead)
    await db.commit()
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="lead", resource_id=lead.id,
                     summary=f"更新线索: {lead.title}")
    return lead


async def qualify_lead(db: AsyncSession, tenant_id: str, lead_id: str, user: dict) -> dict:
    """Convert a lead into a customer."""
    lead = await get_lead(db, tenant_id, lead_id)
    if lead.status == "qualified":
        raise BusinessException(code=LEAD_ALREADY_QUALIFIED, message="线索已转化")
    if lead.status == "discarded":
        raise BusinessException(code=LEAD_ALREADY_DISCARDED, message="线索已废弃，无法转化")

    # Create customer from lead — carry over geographic fields so sales keeps context on conversion
    customer = Customer(
        id=generate_uuid(), tenant_id=tenant_id,
        name=lead.company_name or lead.title,
        industry=lead.industry,
        region=_derived_region(lead) or lead.region,
        source=lead.source, owner_id=lead.owner_id, owner_name=lead.owner_name,
    )
    db.add(customer)

    lead.status = "qualified"
    lead.converted_customer_id = customer.id
    await db.commit()
    await db.refresh(lead)
    await db.refresh(customer)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="qualify", resource_type="lead", resource_id=lead.id,
                     summary=f"转化线索: {lead.title} -> 客户: {customer.name}")

    # Auto-activity: record lead qualification on lead timeline
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "lead", lead.id, "system",
                              f"线索转化为客户: {customer.name}", None,
                              user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for lead qualification failed: %s", e)

    return {"lead_id": lead.id, "customer_id": customer.id, "customer_name": customer.name}


async def delete_lead(db: AsyncSession, tenant_id: str, lead_id: str, user: dict):
    lead = await get_lead(db, tenant_id, lead_id)
    lead_title = lead.title

    if lead.status == "qualified":
        from app.common.error_codes import VALIDATION_ERROR
        raise BusinessException(code=VALIDATION_ERROR, message="已转化的线索不可删除")

    # Soft delete
    lead.is_deleted = True
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="lead", resource_id=lead_id,
                     summary=f"删除线索: {lead_title}")


async def discard_lead(db: AsyncSession, tenant_id: str, lead_id: str, user: dict) -> Lead:
    lead = await get_lead(db, tenant_id, lead_id)
    if lead.status == "qualified":
        raise BusinessException(code=LEAD_ALREADY_QUALIFIED, message="线索已转化，无法废弃")
    if lead.status == "discarded":
        raise BusinessException(code=LEAD_ALREADY_DISCARDED, message="线索已废弃")

    lead.status = "discarded"
    await db.commit()
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="discard", resource_type="lead", resource_id=lead.id,
                     summary=f"废弃线索: {lead.title}")

    # Auto-activity: record lead discard
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "lead", lead.id, "system",
                              "线索已废弃", None,
                              user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for lead discard failed: %s", e)

    return lead
