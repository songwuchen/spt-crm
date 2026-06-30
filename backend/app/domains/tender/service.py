from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.common.code_generator import generate_code
from app.domains.tender.models import Tender
from app.domains.tender.schemas import TenderCreate, TenderUpdate
from app.domains.audit.service import log_action


async def list_tenders(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    customer_id: str | None = None, status: str | None = None, keyword: str | None = None,
    adv_filter: str | None = None, sort_by: str | None = None, sort_order: str | None = None,
    current_user: dict | None = None,
):
    base = select(Tender).where(Tender.tenant_id == tenant_id, Tender.is_deleted == False)
    if customer_id:
        base = base.where(Tender.customer_id == customer_id)
    if status:
        base = base.where(Tender.status == status)
    if keyword:
        base = base.where(Tender.tender_no.ilike(f"%{keyword}%") | Tender.title.ilike(f"%{keyword}%"))

    # 高级筛选（多字段/多条件）
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("tender", adv_filter, {"user_id": (current_user or {}).get("sub")})
    if clause is not None:
        base = base.where(clause)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    order = resolve_sort("tender", sort_by, sort_order) or Tender.created_at.desc()
    items = (await db.execute(
        base.order_by(order).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_tender(db: AsyncSession, tenant_id: str, tender_id: str) -> Tender:
    t = (await db.execute(
        select(Tender).where(Tender.id == tender_id, Tender.tenant_id == tenant_id, Tender.is_deleted == False)
    )).scalar_one_or_none()
    if not t:
        raise BusinessException(code=NOT_FOUND, message="标书不存在")
    return t


async def create_tender(db: AsyncSession, tenant_id: str, data: TenderCreate, user: dict) -> Tender:
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

    tender = Tender(
        id=generate_uuid(), tenant_id=tenant_id,
        tender_no=await generate_code(db, tenant_id, "tender"),
        owner_id=owner_id, owner_name=owner_name,
        **payload,
    )
    db.add(tender)
    await db.commit()
    await db.refresh(tender)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="tender", resource_id=tender.id,
                     summary=f"创建标书: {tender.tender_no}")
    return tender


async def update_tender(db: AsyncSession, tenant_id: str, tender_id: str, data: TenderUpdate, user: dict) -> Tender:
    tender = await get_tender(db, tenant_id, tender_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(tender, field, val)
    await db.commit()
    await db.refresh(tender)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="tender", resource_id=tender.id,
                     summary=f"更新标书: {tender.tender_no}")
    return tender


async def delete_tender(db: AsyncSession, tenant_id: str, tender_id: str, user: dict):
    tender = await get_tender(db, tenant_id, tender_id)
    tender.is_deleted = True
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="tender", resource_id=tender_id,
                     summary=f"删除标书: {tender.tender_no}")
